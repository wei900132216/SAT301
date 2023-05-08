import USBC
import cv2

cam = USBC.USBCamera()
# List of all USB cameras
cam_list = cam.get_camera_list()
# Print information of the selected camera
cam.get_camera_info(cam_list[0])
# Create Camera Object
cam_processor = cam.CameraProcessor(path=cam_list[0]["path"], encode="MJPG", fps=30, width=1920, height=1080)
# Start acquisition thread
cam_processor.start_capture()
# Show the image/video stream
while True:
    frame = cam_processor.frame_queue.get()
    cv2.imshow('latest_frame', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
cam_processor.stop_capture()
