
import glob
import os.path
import queue
import subprocess
import threading
from queue import Queue
import cv2
import v4l2
import fcntl


class USBCamera:

    def get_camera_list(self):
        print('Camera List')
        camera_list=[]
        index = 0
        video_devices = glob.glob('/dev/video*')
        for video_device in video_devices:
            # Extract the device name from the path
            cap = cv2.VideoCapture(video_device)
            if not cap.isOpened():
                continue
            print("Camera " + str(index))
            print(f"Device path: {video_device}")

            # Open the video device
            video_device_file = open(video_device, 'rb+', buffering=0)
            cp = v4l2.v4l2_capability()
            fcntl.ioctl(video_device_file, v4l2.VIDIOC_QUERYCAP, cp)
            device_name = cp.card.decode('utf-8')
            print("Device name:", device_name)
            index +=1
            camera_list.append({'camera name': device_name, 'path': video_device})
        print("")
        return camera_list

    def get_camera_info(self, camera):

        video_device_file = open(camera["path"], 'rb+', buffering=0)
        cp = v4l2.v4l2_capability()
        fcntl.ioctl(video_device_file, v4l2.VIDIOC_QUERYCAP, cp)
        device_name = cp.card.decode('utf-8')
        print("Selected Device:", device_name)

        camera_path = camera["path"]
        camera_file = open(camera_path, 'rb+', buffering=0)
        # Enumerate the supported encoding formats
        fmt = v4l2.v4l2_fmtdesc()
        fmt.type = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
        print("Supported encoding format:")
        while True:
            try:
                fcntl.ioctl(camera_file, v4l2.VIDIOC_ENUM_FMT, fmt)
                print(f"  Encoding format: {fmt.description.decode('utf-8')}")
                fmt.index += 1
            except OSError:
                break

        # Enumerate the supported frame sizes for each encoding format
        fmt.index = 0
        print("Supported Resolution:")
        while True:
            try:
                fcntl.ioctl(camera_file, v4l2.VIDIOC_ENUM_FMT, fmt)
                print(f"  Resolution for {fmt.description.decode('utf-8')}:")
                frmsize = v4l2.v4l2_frmsizeenum()
                frmsize.pixel_format = fmt.pixelformat
                frmsize.index = 0
                while True:
                    try:
                        fcntl.ioctl(camera_file, v4l2.VIDIOC_ENUM_FRAMESIZES, frmsize)
                        if frmsize.type == v4l2.V4L2_FRMSIZE_TYPE_DISCRETE:
                            print(f"    {frmsize.discrete.width}x{frmsize.discrete.height} ")
                        frmivalenum = v4l2.v4l2_frmivalenum()
                        frmivalenum.index = 0
                        frmivalenum.pixel_format = fmt.pixelformat
                        frmivalenum.width = frmsize.discrete.width
                        frmivalenum.height = frmsize.discrete.height

                        while True:
                            try:
                                fcntl.ioctl(camera_file, v4l2.VIDIOC_ENUM_FRAMEINTERVALS, frmivalenum)
                                if frmivalenum.type == v4l2.V4L2_FRMIVAL_TYPE_DISCRETE:
                                    fps = frmivalenum.discrete.denominator / frmivalenum.discrete.numerator
                                    print(f"        {fps}  fps")
                                frmivalenum.index += 1
                            except OSError:
                                break
                        frmsize.index += 1
                    except OSError:
                        break
                fmt.index += 1
            except OSError:
                break

    print("------------------------------------")

    class CameraProcessor:

        def __init__(self, path, encode="MJPG", fps=30, width=1280, height=960):

            self.path = path
            self.encode = encode
            self.fps = fps
            self.width = width
            self.height = height
            self.frame_queue = Queue()

            self.camera_thread = threading.Thread(target=self.capture_frames)

        def start_capture(self):
            self.camera_thread.start()

        def stop_capture(self):
            self.camera_thread.join()

        def capture_frames(self):
            control_value1 = self.encode
            v4l2_command1 = 'v4l2-ctl -d {} --set-fmt-video=width={},height={},pixelformat={}'.format(self.path, self.width, self.height,
                                                                                                      self.encode)
            subprocess.call(v4l2_command1, shell=True)
            # Initialize VideoCapture object
            cap = cv2.VideoCapture(self.path)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*self.encode))
            cap.set(cv2.CAP_PROP_FPS, self.fps)

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


