"""
Smart Park View - Backend Server

Flask server with WebSocket support for real-time parking occupancy detection.
"""

import json
import base64
import cv2
import numpy as np
from io import BytesIO
from PIL import Image
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sock import Sock

from detector import YOLOParkingDetector, CONFIG

app = Flask(__name__)
CORS(app)
sock = Sock(app)

# Initialize detector
print('[Server] Initializing parking detector...')
detector = YOLOParkingDetector()


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'detector': 'YOLOv8' if detector.model is not None else 'fallback',
        'config': detector.get_debug_info().get('config', {})
    })


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current detector configuration."""
    return jsonify(detector.get_debug_info().get('config', {}))


@app.route('/api/config', methods=['POST'])
def update_config():
    """Update detector configuration."""
    data = request.json or {}
    detector.set_config(**data)
    return jsonify({
        'status': 'ok',
        'config': detector.get_debug_info().get('config', {})
    })


@app.route('/api/reset', methods=['POST'])
def reset_detector():
    """Reset detector state."""
    detector.reset()
    return jsonify({'status': 'ok'})


@sock.route('/ws')
def websocket(ws):
    """WebSocket endpoint for real-time frame processing."""
    print('[Server] WebSocket client connected')
    
    while True:
        try:
            message = ws.receive()
            if message is None:
                break
            
            data = json.loads(message)
            
            if data.get('type') == 'frame':
                # Decode base64 image
                frame_data = data['data']
                if ',' in frame_data:
                    frame_data = frame_data.split(',')[1]
                
                image_bytes = base64.b64decode(frame_data)
                image = Image.open(BytesIO(image_bytes))
                frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                
                # Process spots
                spots = data.get('spots', [])
                occupancy_map = detector.detect_occupancy(frame, spots)
                
                # Get debug info
                debug_info = detector.get_debug_info()
                
                # Prepare response (ensure JSON serializable)
                response = {
                    'occupancyMap': {k: bool(v) for k, v in occupancy_map.items()},
                    'debug': {
                        # All YOLO detections for debug overlay
                        'allDetections': [
                            {
                                'x1': int(d['x1']),
                                'y1': int(d['y1']),
                                'x2': int(d['x2']),
                                'y2': int(d['y2']),
                                'conf': float(d['conf']),
                                'cls': d['cls_name'],
                                'isVehicle': bool(d['is_vehicle'])
                            }
                            for d in debug_info.get('all_detections', [])
                        ],
                        # Vehicle detections only
                        'vehicleBoxes': [
                            {
                                'x1': int(d['x1']),
                                'y1': int(d['y1']),
                                'x2': int(d['x2']),
                                'y2': int(d['y2']),
                                'conf': float(d['conf']),
                                'cls': d['cls_name']
                            }
                            for d in debug_info.get('vehicle_detections', [])
                        ],
                        # Per-spot info
                        'spotInfo': {
                            spot_id: {
                                'yoloRatio': float(info.get('yolo_ratio', 0)),
                                'textureScore': float(info.get('texture_score', 0)),
                                'occupied': bool(info.get('is_occupied', False)),
                                'decision': str(info.get('decision', 'UNKNOWN'))
                            }
                            for spot_id, info in debug_info.get('spots', {}).items()
                        }
                    }
                }
                
                ws.send(json.dumps(response))
            
            elif data.get('type') == 'config':
                detector.set_config(**{k: v for k, v in data.items() if k != 'type'})
                ws.send(json.dumps({
                    'type': 'config_updated',
                    'config': detector.get_debug_info().get('config', {})
                }))
            
            elif data.get('type') == 'reset':
                detector.reset()
                ws.send(json.dumps({'type': 'reset_done'}))
                
        except json.JSONDecodeError as e:
            print(f'[Server] JSON error: {e}')
        except Exception as e:
            print(f'[Server] WebSocket error: {e}')
            import traceback
            traceback.print_exc()
            break
    
    print('[Server] WebSocket client disconnected')


if __name__ == '__main__':
    print('[Server] Starting on http://0.0.0.0:5001')
    app.run(host='0.0.0.0', port=5001, debug=True)
