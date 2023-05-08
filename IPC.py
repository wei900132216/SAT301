import queue
import socket
import struct
import subprocess
import threading
from queue import Queue

import cv2
from wsdiscovery import WSDiscovery
from onvif2 import ONVIFCamera


class IPCamera:

    def __init__(self, username, password, port=80):
        self.username = username
        self.password = password
        self.port = port
        self.lst = list()
        self.device_dict = self.get_camera_list(username, password, port)
        self.frame_queue = Queue()
        self.camera_thread = None
        self.cameras_encoder_options_list = self.get_options()

    def get_camera_list(self, username, password, port=80):
        device_dict = {}
        scope = None
        if (scope == None):
            cmd = 'hostname -I'
            scope = subprocess.check_output(cmd, shell=True).decode('utf-8')

        # Find the IP address of the device that supports the ONVIF protocol
        wsd = WSDiscovery()
        wsd.start()
        ret = wsd.searchServices()
        for service in ret:
            get_ip = str(service.getXAddrs())
            get_types = str(service.getTypes())
            for ip_scope in scope.split():
                result = get_ip.find(ip_scope.split('.')[0] + '.' + ip_scope.split('.')[1])
                if result > 0 and get_types.find('onvif') > 0:
                    string_result = get_ip[result:result + 13]
                    string_result = string_result.split('/')[0]
                    self.lst.append(string_result)
        wsd.stop()
        self.lst.sort()
        cam_profiles = {}

        # Walk through all ONVIF devices and get information about the devices.
        for ip in self.lst:

            cam = None
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.01)
            result = sock.connect_ex((ip, port))
            try:
                if result == 0:
                    cam = ONVIFCamera(ip, port, username, password, wsdl_dir='./onvif2/wsdl')
                    sock.close()
                    cam.update_xaddrs()
            except Exception as e:
                device_dict[ip] = dict(
                    error='Network problems are encountered, or the ONVIF port is incorrect, or the ONVIF service is not '
                          'turned on.')
                continue
            try:
                media_service = cam.create_media_service()
                profiles = media_service.GetProfiles()
            except Exception as e:
                device_dict[ip] = dict(
                    error="The user or/and password for the camera's ONVIF service is incorrect. Please check that a user "
                          "has been added to the ONVIF service and that the user name and password are correct.")
                continue
            device_service = cam.create_devicemgmt_service()
            device_info_dict = {'brand': '', 'model': '', 'camsn': ''}
            try:
                device_info = device_service.GetDeviceInformation()
                device_info_dict = {'brand': device_info['Manufacturer'],
                                    'model': device_info['Model'],
                                    'camsn': device_info['SerialNumber']}
            except:
                pass

            for profile in profiles:
                cam_profile = {}
                profile_name = profile['Name']
                cam_profile['Encoding'] = profile['VideoEncoderConfiguration']['Encoding']
                cam_profile['Resolution'] = vars(profile['VideoEncoderConfiguration']['Resolution'])['__values__']
                cam_profile['Quality'] = profile['VideoEncoderConfiguration']['Quality']
                cam_profile['RateControl'] = vars(profile['VideoEncoderConfiguration']['RateControl'])['__values__']

                stream_uri = media_service.GetStreamUri({'StreamSetup': {'Stream': 'RTP-Unicast',
                                                                         'Transport':
                                                                             {'Protocol': 'RTSP'}},
                                                         'ProfileToken': profile.token})
                uri = str(stream_uri['Uri'])
                uri = uri.replace('rtsp://', '')
                cam_profile['stream'] = f'rtsp://{username}:{password}@' + uri
                cam_profiles[profile_name] = cam_profile
                device_info_dict['profiles'] = cam_profiles

            device_dict[ip] = device_info_dict

        print_dict(device_dict)
        return device_dict

    # Walk through all ONVIF devices and get the configuration information supported by the devices
    def get_options(self):

        camera_encoder_list = []
        for ip in self.lst:
            encoder_options_dict = {'ip': ip}
            cam = ONVIFCamera(ip, 80, self.username, self.password, wsdl_dir='./onvif2/wsdl')
            cam.update_xaddrs()
            media_service = cam.create_media2_service()
            encoder_options = media_service.GetVideoEncoderConfigurationOptions()  # list
            encoder_options_list = []
            for option in encoder_options:  # option -> zeep.objects.VideoEncoder2ConfigurationOptions
                encoder_options_list.append(dict(vars(option))['__values__'])
            encoder_options_dict['encoder_options'] = encoder_options_list
            camera_encoder_list.append(encoder_options_dict)

        return camera_encoder_list

    def start_capture(self, ip, encode='H264', width=1280, height=960, quality=3.0, fps=25.0, bitrate=4096):
        self.camera_thread = threading.Thread(target=self.capture_frames, args=(ip, encode, width, height, quality, fps, bitrate,))
        self.camera_thread.start()

    def stop_capture(self):

        self.camera_thread.join()

    def capture_frames(self, ip, encode='H264', width=1280, height=720, quality=3.0, fps=25.0, bitrate=4096):
        encoder_options = None
        for camera_encoder_options in self.cameras_encoder_options_list:
            if camera_encoder_options['ip'] == ip:
                encoder_options = camera_encoder_options
        cam = ONVIFCamera(ip, self.port, self.username, self.password, wsdl_dir='./onvif2/wsdl')
        media_service = cam.create_media2_service()
        profiles = media_service.GetProfiles()
        encoders = media_service.GetVideoEncoderConfigurations()[0]

        # set encoder configuration
        for encoder_option in encoder_options['encoder_options']:
            if encode == encoder_option['Encoding']:
                encoders.Encoding = encode
                for resolutions_available in encoder_option['ResolutionsAvailable']:
                    if width == resolutions_available['Width'] and height == resolutions_available['Height']:
                        encoders.Resolution.Width = width
                        encoders.Resolution.Height = height

                if encoder_option['QualityRange']['Min'] <= quality <= encoder_option['QualityRange']['Max']:
                    encoders.Quality = quality
                for frs in encoder_option['FrameRatesSupported']:
                    if fps == frs:
                        encoders.RateControl.FrameRateLimit = fps
                if encoder_option['BitrateRange']['Min'] <= bitrate <= encoder_option['BitrateRange']['Max']:
                    encoders.RateControl.BitrateLimit = bitrate

        media_service.SetVideoEncoderConfiguration(encoders)





        # create stream uri
        stream_setup = media_service.create_type('GetStreamUri')
        stream_setup.Protocol = 'RTSP'
        stream_setup.ProfileToken = profiles[0].token
        stream_uri = media_service.GetStreamUri(stream_setup)
        uri = stream_uri.replace('rtsp://', '')
        uri = f'rtsp://{self.username}:{self.password}@' + uri

        configurations = media_service.GetVideoEncoderConfigurations()
        for configuration in configurations:

            width = configuration['Resolution']['Width']
            height = configuration['Resolution']['Height']
            dic = {'token': configuration['token'],
                   'encoding': configuration['Encoding'],
                   'ratio': "{}*{}".format(width, height),
                   'fps': configuration['RateControl']['FrameRateLimit'],
                   'bitrate': configuration['RateControl']['BitrateLimit'],
                   'gop': configuration['GovLength'],
                   'profile': configuration['Profile'],
                   'quality': configuration['Quality']}

            print(dic)

        cap = cv2.VideoCapture(uri)

        while True:
            ret, frame = cap.read()
            h, w = frame.shape[:2]
            cv2.putText(frame, "Resolution: {}x{}".format(w, h), (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            # Store the most recent frame in the queue
            try:
                self.frame_queue.put_nowait(frame)
            except queue.Full:
                self.frame_queue.get_nowait()
                self.frame_queue.put_nowait(frame)

    def get_frame(self):
        return self.frame_queue.get()

    def get_encoder_options(self, ip, username, password):
        mycam = ONVIFCamera(ip, 80, username, password, wsdl_dir='./onvif2/wsdl')
        media_service = mycam.create_media2_service()
        options = media_service.GetVideoEncoderConfigurationOptions()
        for opt in options:
            print_dict(dict(vars(opt))['__values__'])
            print("-----------------------------------")

def print_dict(d, indent=0):
    for key, value in d.items():
        if isinstance(value, dict):
            print(f"{' ' * indent}{key}:")
            print_dict(value, indent + 4)
        else:
            print(f"{' ' * indent}{key}: {value}")

