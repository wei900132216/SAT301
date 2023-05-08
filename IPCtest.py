import IPC
import cv2
cam = IPC.IPCamera('admin', 'sat301123')
# List of all cameras
cam_list = cam.lst
# Configuration options
cam.get_encoder_options('192.168.1.64', 'admin', 'sat301123')
# Start acquisition thread
cam.start_capture('192.168.1.64', encode='H264', width=1920, height=1080)
# Show the image/video stream
while True:
    frame = cam.get_frame()
    cv2.imshow('latest_frame', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break