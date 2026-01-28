# Smart Park View

A minimalist web application for tracking occupied and free parking spots using top-view video surveillance.

## Features

- Support for video files, webcam, and IP streams (RTSP/HTTP)
- Interactive parking spot calibration (polygon drawing)
- Real-time occupancy detection using computer vision
- YOLOv8 vehicle detection + edge-based fallback
- Minimalist dark theme UI (black + green accent)
- Configuration persistence via localStorage
- Fullscreen mode with compact HUD

## Technologies

**Frontend:**
- React 18 + TypeScript
- Vite
- Lucide React (icons)
- HTML5 Video + Canvas API

**Backend:**
- Python 3.10+
- Flask + Flask-CORS + Flask-Sock (WebSocket)
- OpenCV for image processing
- YOLOv8 (ultralytics) for vehicle detection

## Installation & Setup

### 1. Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Start server
python app.py
```

Backend will be available at `http://localhost:5001`

### 2. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Frontend will be available at `http://localhost:3000`

### 3. Quick Start (Both Servers)

```bash
./start.sh
```

## Usage

1. Open `http://localhost:3000` in your browser
2. Select video source (file, webcam, or stream)
3. Enter the number of parking spots
4. Click "Start Calibration"
5. For each spot, draw a polygon by clicking on corners
6. After calibration, real-time monitoring begins automatically

## Detection Algorithm

The detector uses a multi-layer approach:

1. **YOLOv8 Detection** — Primary vehicle detection using neural network
2. **Edge-based Fallback** — Detects vehicles by analyzing edge density and intensity variance (works well for top-view)
3. **Diff-based Detection** — Compares current frame to baseline (when spot was empty)
4. **Temporal Smoothing** — Reduces flickering with majority voting over multiple frames
5. **Hysteresis** — Different thresholds for becoming occupied vs becoming free

## Project Structure

```
smart-park-view/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── SetupScreen.tsx       # Setup screen
│   │   │   ├── SidePanel.tsx         # Statistics side panel
│   │   │   ├── VideoPlayer.tsx       # Video player with canvas overlay
│   │   │   ├── CalibrationOverlay.tsx # Calibration UI
│   │   │   └── FullscreenHUD.tsx     # Fullscreen statistics HUD
│   │   ├── hooks/
│   │   │   ├── useFullscreen.ts
│   │   │   └── useVideoProcessor.ts
│   │   ├── utils/
│   │   │   ├── storage.ts            # LocalStorage utilities
│   │   │   └── geometry.ts           # Geometry utilities
│   │   ├── types/
│   │   │   └── index.ts
│   │   ├── styles/
│   │   │   └── index.css
│   │   ├── App.tsx
│   │   └── main.tsx
│   └── public/
├── backend/
│   ├── app.py                        # Flask server
│   ├── detector.py                   # Occupancy detector
│   └── requirements.txt
├── start.sh                          # Quick start script
└── README.md
```

## API

### WebSocket `/ws`

Send frame for processing:
```json
{
  "type": "frame",
  "data": "data:image/jpeg;base64,...",
  "spots": [
    {
      "id": "spot-1",
      "polygon": [{"x": 100, "y": 100}, {"x": 200, "y": 100}, ...]
    }
  ]
}
```

Response:
```json
{
  "occupancyMap": {
    "spot-1": true,
    "spot-2": false
  },
  "debug": {
    "frameSize": [1920, 1080],
    "allDetections": [...],
    "spotInfo": {...}
  }
}
```

### REST Endpoints

- `GET /api/health` — Server health check
- `POST /api/config` — Update detector configuration
- `POST /api/reset` — Reset detector state

## Configuration

Key detector parameters (can be adjusted in `detector.py`):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `confidence_threshold` | 0.15 | YOLO confidence threshold |
| `yolo_threshold_occupied` | 0.12 | Min overlap ratio for occupied |
| `edge_density_threshold_occupied` | 4.5 | Edge density % for occupied |
| `intensity_std_threshold_occupied` | 25.0 | Intensity std for occupied |

## License

MIT
