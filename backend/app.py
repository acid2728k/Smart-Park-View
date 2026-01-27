import json
import base64
import cv2
import numpy as np
from io import BytesIO
from PIL import Image
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sock import Sock

from detector import ParkingDetector

app = Flask(__name__)
CORS(app)
sock = Sock(app)

# Initialize detector
detector = ParkingDetector()

@app.route('/api/health', methods=['GET'])
def health():
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
        
        return jsonify({
            'occupancyMap': occupancy_map
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@sock.route('/ws')
def websocket(ws):
    """WebSocket endpoint for real-time frame processing."""
    print('WebSocket client connected')
    
    while True:
        try:
            message = ws.receive()
            if message is None:
                break
                
            data = json.loads(message)
            
            if data.get('type') == 'frame':
                # Decode base64 image
                frame_data = data['data'].split(',')[1] if ',' in data['data'] else data['data']
                image_bytes = base64.b64decode(frame_data)
                image = Image.open(BytesIO(image_bytes))
                frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                
                # Process spots
                spots = data.get('spots', [])
                occupancy_map = detector.detect_occupancy(frame, spots)
                
                # Send result back
                ws.send(json.dumps({
                    'occupancyMap': occupancy_map
                }))
                
        except Exception as e:
            print(f'WebSocket error: {e}')
            break
    
    print('WebSocket client disconnected')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
