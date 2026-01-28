# Camera & Video Source Setup Guide

This guide explains how to connect different video sources to Smart Park View for parking lot monitoring.

## Table of Contents

1. [Supported Video Sources](#supported-video-sources)
2. [Local Video File](#local-video-file)
3. [USB Webcam](#usb-webcam)
4. [IP Camera (RTSP)](#ip-camera-rtsp)
5. [HTTP Stream (MJPEG)](#http-stream-mjpeg)
6. [Raspberry Pi Camera](#raspberry-pi-camera)
7. [Mobile Phone as Camera](#mobile-phone-as-camera)
8. [Multiple Cameras](#multiple-cameras)
9. [Troubleshooting](#troubleshooting)

---

## Supported Video Sources

| Source Type | Protocol | Example URL |
|-------------|----------|-------------|
| Local File | File API | `video.mp4` (browser file picker) |
| USB Webcam | WebRTC | Browser camera access |
| IP Camera | RTSP | `rtsp://admin:password@192.168.1.100:554/stream1` |
| HTTP Stream | MJPEG/HLS | `http://192.168.1.100:8080/video` |

---

## Local Video File

Best for testing and demos.

### Steps:
1. Open Smart Park View at `http://localhost:3000`
2. Select **"Video File"** from the dropdown
3. Click **"Choose file..."** and select your video
4. Supported formats: MP4, WebM, AVI, MOV

### Requirements:
- Video should be **top-view** (bird's eye view) of parking lot
- Recommended resolution: 1080p or higher
- Recommended frame rate: 15-30 FPS

---

## USB Webcam

Direct connection to your computer.

### Steps:
1. Connect USB webcam to your computer
2. Open Smart Park View at `http://localhost:3000`
3. Select **"Webcam"** from the dropdown
4. Click **"Start Calibration"**
5. Browser will request camera permission — click **Allow**

### Tips:
- Mount camera high above the parking lot for best results
- Ensure good lighting (natural or artificial)
- Use a wide-angle lens if possible

### Supported Browsers:
- Chrome (recommended)
- Firefox
- Edge
- Safari (macOS)

---

## IP Camera (RTSP)

Most professional IP cameras support RTSP streaming.

### Common RTSP URL Formats:

```
# Generic format
rtsp://username:password@camera_ip:port/path

# Hikvision
rtsp://admin:password@192.168.1.64:554/Streaming/Channels/101

# Dahua
rtsp://admin:password@192.168.1.108:554/cam/realmonitor?channel=1&subtype=0

# Axis
rtsp://root:password@192.168.1.90:554/axis-media/media.amp

# Reolink
rtsp://admin:password@192.168.1.100:554/h264Preview_01_main

# Amcrest
rtsp://admin:password@192.168.1.100:554/cam/realmonitor?channel=1&subtype=0

# TP-Link Tapo
rtsp://username:password@192.168.1.100:554/stream1

# Ubiquiti UniFi
rtsp://192.168.1.100:7447/camera_id
```

### Backend Proxy Setup (Required for RTSP)

Browsers cannot directly access RTSP streams. You need to set up a proxy server.

#### Option 1: FFmpeg + HTTP (Recommended)

Install FFmpeg:
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

Start the proxy:
```bash
ffmpeg -rtsp_transport tcp -i "rtsp://admin:password@192.168.1.100:554/stream1" \
  -c:v libx264 -preset ultrafast -tune zerolatency \
  -f hls -hls_time 1 -hls_list_size 3 -hls_flags delete_segments \
  /var/www/html/stream/playlist.m3u8
```

Then use in Smart Park View:
```
http://localhost/stream/playlist.m3u8
```

#### Option 2: mediamtx (Simple RTSP to WebRTC)

```bash
# Download mediamtx from https://github.com/bluenviron/mediamtx
./mediamtx
```

Configure `mediamtx.yml`:
```yaml
paths:
  parking:
    source: rtsp://admin:password@192.168.1.100:554/stream1
```

Access at: `http://localhost:8889/parking`

#### Option 3: go2rtc

```bash
# Download from https://github.com/AlexxIT/go2rtc
./go2rtc
```

Configure `go2rtc.yaml`:
```yaml
streams:
  parking: rtsp://admin:password@192.168.1.100:554/stream1
```

Access at: `http://localhost:1984/api/stream.mp4?src=parking`

---

## HTTP Stream (MJPEG)

Some cameras provide direct HTTP/MJPEG streams.

### Steps:
1. Find your camera's HTTP stream URL (check camera documentation)
2. Select **"IP Stream (RTSP/HTTP)"** in Smart Park View
3. Enter the URL, e.g.: `http://192.168.1.100:8080/video`

### Common MJPEG URLs:

```
# Generic webcam server
http://192.168.1.100:8080/video

# ESP32-CAM
http://192.168.1.100:81/stream

# Android IP Webcam app
http://192.168.1.100:8080/video
```

---

## Raspberry Pi Camera

Use Raspberry Pi as a dedicated camera server.

### Hardware Required:
- Raspberry Pi 3/4/5
- Raspberry Pi Camera Module (v2 or HQ)
- Power supply
- MicroSD card

### Setup Steps:

1. **Install Raspberry Pi OS** (Lite or Full)

2. **Enable camera:**
   ```bash
   sudo raspi-config
   # Navigate to: Interface Options > Camera > Enable
   ```

3. **Install streaming software:**
   ```bash
   # Option A: Motion (simple)
   sudo apt install motion
   
   # Option B: mjpg-streamer (lightweight)
   sudo apt install cmake libjpeg-dev
   git clone https://github.com/jacksonliam/mjpg-streamer.git
   cd mjpg-streamer/mjpg-streamer-experimental
   make
   sudo make install
   ```

4. **Start streaming:**
   ```bash
   # Motion
   sudo motion
   # Stream at: http://raspberrypi.local:8081
   
   # mjpg-streamer
   mjpg_streamer -i "input_raspicam.so -fps 15 -x 1920 -y 1080" \
                 -o "output_http.so -p 8080 -w /usr/local/share/mjpg-streamer/www"
   # Stream at: http://raspberrypi.local:8080/?action=stream
   ```

5. **Use in Smart Park View:**
   - Select "IP Stream (RTSP/HTTP)"
   - Enter: `http://raspberrypi.local:8080/?action=stream`

### Tips for Outdoor Installation:
- Use weatherproof enclosure
- Power via PoE (Power over Ethernet) if possible
- Consider IR camera for night vision

---

## Mobile Phone as Camera

Use your smartphone as a wireless camera.

### Android (IP Webcam App)

1. Install **"IP Webcam"** from Google Play Store
2. Open app and configure:
   - Resolution: 1080p
   - Quality: 80%
   - Orientation: Landscape
3. Tap **"Start server"**
4. Note the IP address shown (e.g., `http://192.168.1.50:8080`)
5. In Smart Park View, use: `http://192.168.1.50:8080/video`

### iPhone (Camera Live App)

1. Install **"Camera Live"** or similar RTSP server app
2. Start streaming
3. Use the provided RTSP URL with a proxy (see RTSP section)

### Tips:
- Keep phone plugged in (streaming drains battery)
- Disable screen timeout
- Use phone mount for stable positioning
- Connect to Wi-Fi (not mobile data)

---

## Multiple Cameras

To monitor multiple parking areas:

### Option 1: Multiple Browser Tabs
- Open Smart Park View in multiple tabs
- Configure each with different video source

### Option 2: Video Multiplexer
Use FFmpeg to combine multiple streams:

```bash
ffmpeg -i "rtsp://camera1" -i "rtsp://camera2" \
  -filter_complex "[0:v][1:v]hstack=inputs=2[v]" \
  -map "[v]" -f hls output.m3u8
```

### Option 3: Modify Application (Advanced)
The application can be extended to support multiple video sources simultaneously. This requires code modifications to:
- Handle multiple WebSocket connections
- Display multiple video players
- Aggregate statistics

---

## Troubleshooting

### Camera not detected (Webcam)
- Check browser permissions (click lock icon in address bar)
- Try different browser (Chrome recommended)
- Check if camera works in other apps
- Restart browser

### RTSP stream not working
- Verify URL format matches your camera model
- Check username/password
- Ensure camera and computer are on same network
- Try VLC to test stream: `vlc rtsp://...`
- Use proxy server (browsers don't support RTSP directly)

### Video lag/delay
- Reduce resolution in camera settings
- Use hardware encoding (H.264)
- Check network bandwidth
- Use wired connection instead of Wi-Fi

### Detection not working
- Ensure camera is mounted with **top-view angle**
- Improve lighting conditions
- Adjust detection thresholds in `backend/detector.py`
- Check if video resolution is sufficient (min 720p recommended)

### Connection timeout
- Check firewall settings
- Verify camera IP address
- Ping camera: `ping 192.168.1.100`
- Check camera web interface is accessible

---

## Recommended Camera Specifications

For best detection results:

| Parameter | Minimum | Recommended |
|-----------|---------|-------------|
| Resolution | 720p | 1080p or 4K |
| Frame Rate | 10 FPS | 15-30 FPS |
| Field of View | 90° | 120°+ (wide angle) |
| Night Vision | - | IR LEDs for 24/7 |
| Mounting Height | 3m | 5-10m |
| Angle | Top-view | Directly overhead |

---

## Need Help?

If you encounter issues:
1. Check the [Troubleshooting](#troubleshooting) section
2. Open an issue on GitHub with:
   - Camera model
   - Video source type
   - Error message (if any)
   - Browser console logs
