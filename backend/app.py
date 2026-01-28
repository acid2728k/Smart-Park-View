"""
Smart Park View - Backend Server
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

from detector import YOLOParkingDetector

app = Flask(__name__)
CORS(app)
sock = Sock(app)

print('[Server] Initializing detector...')
detector = YOLOParkingDetector()


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'detector': 'YOLOv8' if detector.model else 'fallback',
        'config': detector.get_debug_info().get('config', {})
    })


@app.route('/api/config', methods=['POST'])
def update_config():
    data = request.json or {}
    detector.set_config(**data)
    return jsonify({'status': 'ok', 'config': detector.get_debug_info().get('config', {})})


@app.route('/api/reset', methods=['POST'])
def reset_detector():
    detector.reset()
    return jsonify({'status': 'ok'})


def safe_json(obj):
    """Convert numpy types to JSON-serializable Python types."""
    if isinstance(obj, dict):
        return {k: safe_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [safe_json(v) for v in obj]
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    return obj


@sock.route('/ws')
def websocket(ws):
    print('[Server] WebSocket connected')
    
    while True:
        try:
            message = ws.receive()
            if message is None:
                break
            
            data = json.loads(message)
            
            if data.get('type') == 'frame':
                frame_data = data['data']
                if ',' in frame_data:
                    frame_data = frame_data.split(',')[1]
                
                image_bytes = base64.b64decode(frame_data)
                image = Image.open(BytesIO(image_bytes))
                frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                
                spots = data.get('spots', [])
                occupancy_map = detector.detect_occupancy(frame, spots)
                debug_info = detector.get_debug_info()
                
                # Build response
                response = {
                    'occupancyMap': {k: bool(v) for k, v in occupancy_map.items()},
                    'debug': {
                        'frameSize': list(debug_info.get('frame_size', [0, 0])),
                        # All raw detections for debug overlay
                        'allDetections': [
                            {
                                'x1': int(d['x1']),
                                'y1': int(d['y1']),
                                'x2': int(d['x2']),
                                'y2': int(d['y2']),
                                'conf': float(d['conf']),
                                'cls': str(d['cls_name']),
                                'isVehicle': bool(d.get('is_vehicle', False)),
                                'isIgnored': bool(d.get('is_ignored', False))
                            }
                            for d in debug_info.get('raw_detections', [])
                        ],
                        # Vehicles only
                        'vehicleBoxes': [
                            {
                                'x1': int(d['x1']),
                                'y1': int(d['y1']),
                                'x2': int(d['x2']),
                                'y2': int(d['y2']),
                                'conf': float(d['conf']),
                                'cls': str(d['cls_name'])
                            }
                            for d in debug_info.get('vehicle_detections', [])
                        ],
                        # Per-spot info
                        'spotInfo': {
                            spot_id: safe_json({
                                'yoloRatio': info.get('yolo_ratio', 0),
                                'edgeDensity': info.get('edge_density', 0),
                                'intensityStd': info.get('intensity_std', 0),
                                'diffMean': info.get('diff_mean', 0),
                                'changedRatio': info.get('changed_ratio', 0),
                                'occupied': info.get('is_occupied', False),
                                'decision': info.get('decision', 'UNKNOWN'),
                                'baselineValid': info.get('baseline_valid', False),
                                'baselineAge': info.get('baseline_age', -1),
                                'consecutiveFree': info.get('consecutive_free', 0),
                                'bestDet': info.get('best_det', {}),
                                'thresholds': info.get('thresholds', {})
                            })
                            for spot_id, info in debug_info.get('spots', {}).items()
                        },
                        'config': safe_json(debug_info.get('config', {}))
                    }
                }
                
                ws.send(json.dumps(response))
            
            elif data.get('type') == 'config':
                detector.set_config(**{k: v for k, v in data.items() if k != 'type'})
                ws.send(json.dumps({
                    'type': 'config_updated',
                    'config': safe_json(detector.get_debug_info().get('config', {}))
                }))
            
            elif data.get('type') == 'reset':
                detector.reset()
                ws.send(json.dumps({'type': 'reset_done'}))
                
        except json.JSONDecodeError as e:
            print(f'[Server] JSON error: {e}')
        except Exception as e:
            print(f'[Server] Error: {e}')
            import traceback
            traceback.print_exc()
            break
    
    print('[Server] WebSocket disconnected')


if __name__ == '__main__':
    print('[Server] Starting on http://0.0.0.0:5001')
    app.run(host='0.0.0.0', port=5001, debug=True)
