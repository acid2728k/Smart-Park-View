import cv2
import numpy as np
from typing import List, Dict, Any, Tuple
from collections import deque


# Configuration
OVERLAP_THRESHOLD = 0.30  # 30% overlap to consider occupied


class YOLOParkingDetector:
    """
    Parking spot occupancy detector using YOLOv8 for vehicle detection.
    Compares detected vehicle bounding boxes with parking spot polygons
    using Intersection over Area (IoA) metric.
    """
    
    def __init__(self, model_path: str = 'yolov8n.pt', overlap_threshold: float = OVERLAP_THRESHOLD):
        self.model = None
        self.model_path = model_path
        self.overlap_threshold = overlap_threshold
        self._load_model()
        
        # Vehicle class IDs in COCO dataset
        # 2: car, 3: motorcycle, 5: bus, 7: truck
        self.vehicle_classes = [2, 3, 5, 7]
        
        # History for temporal smoothing (reduces flickering)
        self.history: Dict[str, deque] = {}
        self.history_size = 3  # Reduced for faster response
        
        # Cache for detected vehicles (for debugging/visualization)
        self.last_detections: List[Tuple[int, int, int, int, float]] = []
    
    def _load_model(self):
        """Load YOLO model."""
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_path)
            # Warm up the model
            print(f'YOLOv8 model loaded successfully: {self.model_path}')
        except ImportError:
            print('ERROR: ultralytics not installed. Run: pip install ultralytics')
            self.model = None
        except Exception as e:
            print(f'ERROR: Failed to load YOLO model: {e}')
            self.model = None
    
    def detect_occupancy(self, frame: np.ndarray, spots: List[Dict[str, Any]]) -> Dict[str, bool]:
        """
        Detect occupancy for each parking spot using YOLO vehicle detection.
        
        Args:
            frame: BGR image frame from video
            spots: List of parking spots with 'id' and 'polygon' keys
            
        Returns:
            Dictionary mapping spot IDs to occupancy status (True = occupied)
        """
        if self.model is None:
            print('YOLO model not loaded, using fallback detector')
            return self._fallback_detection(frame, spots)
        
        if frame is None or len(spots) == 0:
            return {}
        
        # Run YOLO detection
        try:
            results = self.model(frame, verbose=False, conf=0.25)[0]
        except Exception as e:
            print(f'YOLO detection error: {e}')
            return self._fallback_detection(frame, spots)
        
        # Extract vehicle bounding boxes
        vehicle_boxes = []
        for box in results.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            
            if cls_id in self.vehicle_classes and conf > 0.3:
                x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                vehicle_boxes.append((x1, y1, x2, y2, conf))
        
        self.last_detections = vehicle_boxes
        print(f'Detected {len(vehicle_boxes)} vehicles')
        
        # Check each parking spot
        occupancy_map = {}
        
        for spot in spots:
            spot_id = spot.get('id')
            polygon = spot.get('polygon', [])
            
            if not spot_id or len(polygon) < 3:
                continue
            
            # Convert polygon to numpy array
            pts = np.array([[int(p['x']), int(p['y'])] for p in polygon], dtype=np.int32)
            spot_area = cv2.contourArea(pts)
            
            if spot_area < 100:
                occupancy_map[spot_id] = False
                continue
            
            # Check overlap with each vehicle
            is_occupied = False
            max_overlap = 0.0
            
            for (x1, y1, x2, y2, conf) in vehicle_boxes:
                intersection_area = self._calculate_intersection(pts, (x1, y1, x2, y2))
                overlap_ratio = intersection_area / spot_area if spot_area > 0 else 0
                max_overlap = max(max_overlap, overlap_ratio)
                
                if overlap_ratio >= self.overlap_threshold:
                    is_occupied = True
                    break
            
            # Apply temporal smoothing
            is_occupied = self._smooth_occupancy(spot_id, is_occupied)
            occupancy_map[spot_id] = is_occupied
            
            print(f'Spot {spot_id}: overlap={max_overlap:.2f}, occupied={is_occupied}')
        
        return occupancy_map
    
    def _calculate_intersection(self, polygon: np.ndarray, box: Tuple[int, int, int, int]) -> float:
        """
        Calculate intersection area between a polygon and a bounding box.
        """
        x1, y1, x2, y2 = box
        
        # Get bounds
        poly_x_min, poly_y_min = polygon.min(axis=0)
        poly_x_max, poly_y_max = polygon.max(axis=0)
        
        # Quick check - if no overlap in bounding boxes, return 0
        if x2 < poly_x_min or x1 > poly_x_max or y2 < poly_y_min or y1 > poly_y_max:
            return 0
        
        # Create masks for accurate intersection calculation
        # Use the bounding rectangle that contains both shapes
        min_x = max(0, min(x1, poly_x_min))
        min_y = max(0, min(y1, poly_y_min))
        max_x = max(x2, poly_x_max) + 1
        max_y = max(y2, poly_y_max) + 1
        
        # Offset polygon and box to local coordinates
        local_polygon = polygon - np.array([min_x, min_y])
        local_box = np.array([
            [x1 - min_x, y1 - min_y],
            [x2 - min_x, y1 - min_y],
            [x2 - min_x, y2 - min_y],
            [x1 - min_x, y2 - min_y]
        ], dtype=np.int32)
        
        h = max_y - min_y
        w = max_x - min_x
        
        # Create masks
        mask_poly = np.zeros((h, w), dtype=np.uint8)
        mask_box = np.zeros((h, w), dtype=np.uint8)
        
        cv2.fillPoly(mask_poly, [local_polygon], 255)
        cv2.fillPoly(mask_box, [local_box], 255)
        
        # Calculate intersection
        intersection = cv2.bitwise_and(mask_poly, mask_box)
        return cv2.countNonZero(intersection)
    
    def _smooth_occupancy(self, spot_id: str, current_state: bool) -> bool:
        """
        Apply temporal smoothing using majority voting.
        """
        if spot_id not in self.history:
            self.history[spot_id] = deque(maxlen=self.history_size)
        
        self.history[spot_id].append(current_state)
        
        # Majority voting
        occupied_count = sum(self.history[spot_id])
        return occupied_count > len(self.history[spot_id]) / 2
    
    def _fallback_detection(self, frame: np.ndarray, spots: List[Dict[str, Any]]) -> Dict[str, bool]:
        """
        Fallback detection using edge density when YOLO is not available.
        """
        if frame is None or len(spots) == 0:
            return {}
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        
        occupancy_map = {}
        
        for spot in spots:
            spot_id = spot.get('id')
            polygon = spot.get('polygon', [])
            
            if not spot_id or len(polygon) < 3:
                continue
            
            pts = np.array([[int(p['x']), int(p['y'])] for p in polygon], dtype=np.int32)
            mask = np.zeros(gray.shape, dtype=np.uint8)
            cv2.fillPoly(mask, [pts], 255)
            
            area = cv2.contourArea(pts)
            if area < 100:
                occupancy_map[spot_id] = False
                continue
            
            masked_edges = cv2.bitwise_and(edges, edges, mask=mask)
            edge_count = cv2.countNonZero(masked_edges)
            edge_ratio = edge_count / area if area > 0 else 0
            
            # Higher threshold for edge-based detection
            is_occupied = edge_ratio > 0.12
            is_occupied = self._smooth_occupancy(spot_id, is_occupied)
            occupancy_map[spot_id] = is_occupied
        
        return occupancy_map
    
    def reset(self):
        """Reset detector state."""
        self.history.clear()
        self.last_detections = []
    
    def set_overlap_threshold(self, threshold: float):
        """Set the overlap threshold for occupancy detection."""
        self.overlap_threshold = max(0.1, min(0.9, threshold))
        print(f'Overlap threshold set to: {self.overlap_threshold}')


# Create a default detector instance
# This will be used by the Flask app
ParkingDetector = YOLOParkingDetector
