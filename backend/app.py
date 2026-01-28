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

from detector import YOLOParkingDetector

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
        'debug': detector.get_debug_info().get('config', {})
    })


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current detector configuration."""
    return jsonify(detector.get_debug_info().get('config', {}))


@app.route('/api/config', methods=['POST'])
def update_config():
    """Update detector configuration."""
    data = request.json or {}
    
    detector.set_config(
        threshold_occupied=data.get('threshold_occupied'),
        threshold_free=data.get('threshold_free'),
        history_size=data.get('history_size'),
        debug_enabled=data.get('debug_enabled')
    )
    
    return jsonify({
        'status': 'ok',
        'config': detector.get_debug_info().get('config', {})
    })


@app.route('/api/reset', methods=['POST'])
def reset_detector():
    """Reset detector state."""
    detector.reset()
    return jsonify({'status': 'ok'})


@app.route('/api/process-frame', methods=['POST'])
def process_frame():
    """Process a single frame and return occupancy status."""
    data = request.json
    
    if not data or 'frame' not in data or 'spots' not in data:
        return jsonify({'error': 'Missing frame or spots data'}), 400
    
    try:
        # Decode base64 image
        frame_data = data['frame'].split(',')[1] if ',' in data['frame'] else data['frame']
        image_bytes = base64.b64decode(frame_data)
        image = Image.open(BytesIO(image_bytes))
        frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # Process spots
        spots = data['spots']
        occupancy_map = detector.detect_occupancy(frame, spots)
        
        # Get debug info
        debug_info = detector.get_debug_info()
        
        return jsonify({
            'occupancyMap': occupancy_map,
            'debug': {
                'detections': len(debug_info['detections']),
                'spots': debug_info['spots']
            }
        })
    except Exception as e:
        print(f'[Server] Error processing frame: {e}')
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


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
                
                # Get debug info for frontend visualization
                debug_info = detector.get_debug_info()
                
                # Prepare response with detection boxes for overlay
                # Ensure all values are JSON serializable (convert numpy types)
                response = {
                    'occupancyMap': {k: bool(v) for k, v in occupancy_map.items()},
                    'debug': {
                        'vehicleBoxes': [
                            {'x1': int(x1), 'y1': int(y1), 'x2': int(x2), 'y2': int(y2), 'conf': float(conf)}
                            for (x1, y1, x2, y2, conf, cls_id) in debug_info['detections']
                        ],
                        'spotInfo': {
                            spot_id: {
                                'ratio': float(info['max_ratio']),
                                'occupied': bool(info['is_occupied'])
                            }
                            for spot_id, info in debug_info['spots'].items()
                        }
                    }
                }
                
                ws.send(json.dumps(response))
            
            elif data.get('type') == 'config':
                # Update config via WebSocket
                detector.set_config(
                    threshold_occupied=data.get('threshold_occupied'),
                    threshold_free=data.get('threshold_free'),
                    debug_enabled=data.get('debug_enabled')
                )
                ws.send(json.dumps({
                    'type': 'config_updated',
                    'config': detector.get_debug_info().get('config', {})
                }))
            
            elif data.get('type') == 'reset':
                detector.reset()
                ws.send(json.dumps({'type': 'reset_done'}))
                
        except json.JSONDecodeError as e:
            print(f'[Server] JSON decode error: {e}')
        except Exception as e:
            print(f'[Server] WebSocket error: {e}')
            import traceback
            traceback.print_exc()
            break
    
    print('[Server] WebSocket client disconnected')


if __name__ == '__main__':
    print('[Server] Starting on http://0.0.0.0:5001')
    app.run(host='0.0.0.0', port=5001, debug=True)
