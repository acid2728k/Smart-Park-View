import cv2
import numpy as np
from typing import List, Dict, Any, Optional
from collections import deque


class ParkingDetector:
    """
    Parking spot occupancy detector using background subtraction and
    pixel analysis within defined polygonal regions.
    
    This approach is based on common parking detection techniques:
    1. Extract ROI (Region of Interest) for each parking spot
    2. Convert to grayscale and apply edge detection
    3. Count non-zero pixels (edges) in the region
    4. Compare against threshold to determine occupancy
    """
    
    def __init__(self):
        # Background subtractor for motion detection
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500,
            varThreshold=16,
            detectShadows=True
        )
        
        # Store recent occupancy states for smoothing (reduces flickering)
        self.history: Dict[str, deque] = {}
        self.history_size = 5
        
        # Thresholds
        self.edge_threshold = 50  # Minimum edge pixels to consider occupied
        self.occupancy_ratio_threshold = 0.15  # Ratio of non-zero pixels
        
    def detect_occupancy(self, frame: np.ndarray, spots: List[Dict[str, Any]]) -> Dict[str, bool]:
        """
        Detect occupancy for each parking spot in the frame.
        
        Args:
            frame: BGR image frame
            spots: List of spots with 'id' and 'polygon' keys
            
        Returns:
            Dictionary mapping spot IDs to occupancy status (True = occupied)
        """
        if frame is None or len(spots) == 0:
            return {}
        
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Edge detection using Canny
        edges = cv2.Canny(blurred, 50, 150)
        
        # Apply background subtraction
        fg_mask = self.bg_subtractor.apply(frame)
        
        occupancy_map = {}
        
        for spot in spots:
            spot_id = spot.get('id')
            polygon = spot.get('polygon', [])
            
            if not spot_id or len(polygon) < 3:
                continue
            
            # Convert polygon to numpy array
            pts = np.array([[p['x'], p['y']] for p in polygon], dtype=np.int32)
            
            # Create mask for this spot
            mask = np.zeros(gray.shape, dtype=np.uint8)
            cv2.fillPoly(mask, [pts], 255)
            
            # Calculate area of the polygon
            area = cv2.contourArea(pts)
            if area < 100:  # Skip very small regions
                occupancy_map[spot_id] = False
                continue
            
            # Method 1: Edge detection analysis
            masked_edges = cv2.bitwise_and(edges, edges, mask=mask)
            edge_count = cv2.countNonZero(masked_edges)
            edge_ratio = edge_count / area if area > 0 else 0
            
            # Method 2: Intensity variance analysis
            masked_gray = cv2.bitwise_and(blurred, blurred, mask=mask)
            # Get pixels within the mask
            spot_pixels = masked_gray[mask > 0]
            if len(spot_pixels) > 0:
                intensity_std = np.std(spot_pixels)
            else:
                intensity_std = 0
            
            # Method 3: Foreground mask (motion/objects)
            masked_fg = cv2.bitwise_and(fg_mask, fg_mask, mask=mask)
            fg_count = cv2.countNonZero(masked_fg)
            fg_ratio = fg_count / area if area > 0 else 0
            
            # Combined decision
            # A spot is considered occupied if:
            # - High edge density (car edges), OR
            # - High intensity variance (texture from car), OR
            # - Significant foreground detection
            is_occupied = (
                edge_ratio > self.occupancy_ratio_threshold or
                intensity_std > 30 or
                fg_ratio > 0.3
            )
            
            # Apply temporal smoothing
            is_occupied = self._smooth_occupancy(spot_id, is_occupied)
            
            occupancy_map[spot_id] = is_occupied
        
        return occupancy_map
    
    def _smooth_occupancy(self, spot_id: str, current_state: bool) -> bool:
        """
        Apply temporal smoothing to reduce flickering between occupied/free states.
        Uses majority voting over recent frames.
        """
        if spot_id not in self.history:
            self.history[spot_id] = deque(maxlen=self.history_size)
        
        self.history[spot_id].append(current_state)
        
        # Majority voting
        occupied_count = sum(self.history[spot_id])
        return occupied_count > len(self.history[spot_id]) / 2
    
    def reset(self):
        """Reset the detector state."""
        self.history.clear()
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500,
            varThreshold=16,
            detectShadows=True
        )


class YOLOParkingDetector:
    """
    Alternative detector using YOLO for vehicle detection.
    Requires ultralytics package and YOLOv8 model.
    
    To use:
    1. pip install ultralytics
    2. Download YOLOv8 model (e.g., yolov8n.pt)
    """
    
    def __init__(self, model_path: str = 'yolov8n.pt'):
        self.model = None
        self.model_path = model_path
        self._load_model()
        
        # Vehicle class IDs in COCO dataset
        self.vehicle_classes = [2, 3, 5, 7]  # car, motorcycle, bus, truck
        
        # History for smoothing
        self.history: Dict[str, deque] = {}
        self.history_size = 5
    
    def _load_model(self):
        """Load YOLO model if available."""
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_path)
            print(f'YOLO model loaded: {self.model_path}')
        except ImportError:
            print('ultralytics not installed, YOLO detector unavailable')
        except Exception as e:
            print(f'Failed to load YOLO model: {e}')
    
    def detect_occupancy(self, frame: np.ndarray, spots: List[Dict[str, Any]]) -> Dict[str, bool]:
        """Detect occupancy using YOLO object detection."""
        if self.model is None or frame is None or len(spots) == 0:
            return {}
        
        # Run YOLO detection
        results = self.model(frame, verbose=False)[0]
        
        # Get vehicle bounding boxes
        vehicle_boxes = []
        for box in results.boxes:
            cls_id = int(box.cls[0])
            if cls_id in self.vehicle_classes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                vehicle_boxes.append((x1, y1, x2, y2))
        
        occupancy_map = {}
        
        for spot in spots:
            spot_id = spot.get('id')
            polygon = spot.get('polygon', [])
            
            if not spot_id or len(polygon) < 3:
                continue
            
            pts = np.array([[p['x'], p['y']] for p in polygon], dtype=np.int32)
            spot_area = cv2.contourArea(pts)
            
            if spot_area < 100:
                occupancy_map[spot_id] = False
                continue
            
            # Check if any vehicle overlaps with this spot
            is_occupied = False
            for (x1, y1, x2, y2) in vehicle_boxes:
                # Calculate intersection
                intersection = self._polygon_box_intersection(pts, (x1, y1, x2, y2))
                ioa = intersection / spot_area if spot_area > 0 else 0
                
                if ioa > 0.3:  # 30% overlap threshold
                    is_occupied = True
                    break
            
            # Apply smoothing
            is_occupied = self._smooth_occupancy(spot_id, is_occupied)
            occupancy_map[spot_id] = is_occupied
        
        return occupancy_map
    
    def _polygon_box_intersection(self, polygon: np.ndarray, box: tuple) -> float:
        """Calculate intersection area between polygon and bounding box."""
        x1, y1, x2, y2 = box
        
        # Create box polygon
        box_pts = np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.int32)
        
        # Create masks
        h = max(polygon[:, 1].max(), y2) + 1
        w = max(polygon[:, 0].max(), x2) + 1
        
        mask1 = np.zeros((h, w), dtype=np.uint8)
        mask2 = np.zeros((h, w), dtype=np.uint8)
        
        cv2.fillPoly(mask1, [polygon], 255)
        cv2.fillPoly(mask2, [box_pts], 255)
        
        intersection = cv2.bitwise_and(mask1, mask2)
        return cv2.countNonZero(intersection)
    
    def _smooth_occupancy(self, spot_id: str, current_state: bool) -> bool:
        """Apply temporal smoothing."""
        if spot_id not in self.history:
            self.history[spot_id] = deque(maxlen=self.history_size)
        
        self.history[spot_id].append(current_state)
        occupied_count = sum(self.history[spot_id])
        return occupied_count > len(self.history[spot_id]) / 2
