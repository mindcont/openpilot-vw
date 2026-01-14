import av
import cv2
import numpy as np
import subprocess

RTSP = "rtsp://admin:xxx@192.168.8.202:554/h264/ch1/main/av_stream"

container = av.open(RTSP, options={
    "rtsp_transport": "tcp",
    "fflags": "nobuffer",
    "flags": "low_delay"
})

# v4l2 输出
ffmpeg = subprocess.Popen([
    "ffmpeg",
    "-f", "rawvideo",
    "-pix_fmt", "bgr24",
    "-s", "1280x720",
    "-i", "-",
    "-f", "v4l2",
    "/dev/video10"
], stdin=subprocess.PIPE)

for frame in container.decode(video=0):
    img = frame.to_ndarray(format="bgr24")
    ffmpeg.stdin.write(img.tobytes())
