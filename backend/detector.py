"""
Parking spot occupancy detector using YOLOv8.

Features:
- Accurate polygon-bbox intersection calculation
- Hysteresis thresholds to prevent flickering
- Temporal smoothing with majority voting
- Debug mode for diagnostics
"""

import cv2
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from collections import deque
from dataclasses import dataclass, field


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class DetectorConfig:
    """Configuration for occupancy detection."""
    # Hysteresis thresholds
    threshold_occupied: float = 0.20  # Become occupied if overlap >= this
    threshold_free: float = 0.12      # Become free if overlap < this
    
    # Temporal smoothing
    history_size: int = 10            # Number of frames to remember
    min_consecutive_for_change: int = 3  # Require N consecutive same states
    
    # YOLO settings
    confidence_threshold: float = 0.25
    
    # Debug
    debug_enabled: bool = True


# Global config instance
CONFIG = DetectorConfig()


# =============================================================================
# Geometry utilities
# =============================================================================

def polygon_area(polygon: np.ndarray) -> float:
    """Calculate area of a polygon using Shoelace formula."""
    n = len(polygon)
    if n < 3:
        return 0.0
    
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += polygon[i][0] * polygon[j][1]
        area -= polygon[j][0] * polygon[i][1]
    return abs(area) / 2.0


def polygon_bbox_intersection_area(polygon: np.ndarray, bbox: Tuple[int, int, int, int]) -> float:
    """
    Calculate the intersection area between a polygon and a bounding box.
    Uses OpenCV to create masks and compute intersection.
    
    Args:
        polygon: numpy array of shape (N, 2) with polygon vertices
        bbox: tuple (x1, y1, x2, y2) of bounding box
        
    Returns:
        Intersection area in pixels
    """
    x1, y1, x2, y2 = bbox
    
    # Get bounds for the working area
    poly_x_min = int(polygon[:, 0].min())
    poly_y_min = int(polygon[:, 1].min())
    poly_x_max = int(polygon[:, 0].max())
    poly_y_max = int(polygon[:, 1].max())
    
    # Quick rejection test
    if x2 <= poly_x_min or x1 >= poly_x_max or y2 <= poly_y_min or y1 >= poly_y_max:
        return 0.0
    
    # Create working area that contains both shapes
    min_x = max(0, min(x1, poly_x_min) - 1)
    min_y = max(0, min(y1, poly_y_min) - 1)
    max_x = max(x2, poly_x_max) + 2
    max_y = max(y2, poly_y_max) + 2
    
    h = max_y - min_y
    w = max_x - min_x
    
    if h <= 0 or w <= 0:
        return 0.0
    
    # Offset coordinates to local space
    local_polygon = polygon.copy().astype(np.int32)
    local_polygon[:, 0] -= min_x
    local_polygon[:, 1] -= min_y
    
    local_bbox = np.array([
        [x1 - min_x, y1 - min_y],
        [x2 - min_x, y1 - min_y],
        [x2 - min_x, y2 - min_y],
        [x1 - min_x, y2 - min_y]
    ], dtype=np.int32)
    
    # Create masks
    mask_poly = np.zeros((h, w), dtype=np.uint8)
    mask_bbox = np.zeros((h, w), dtype=np.uint8)
    
    cv2.fillPoly(mask_poly, [local_polygon], 255)
    cv2.fillPoly(mask_bbox, [local_bbox], 255)
    
    # Compute intersection
    intersection = cv2.bitwise_and(mask_poly, mask_bbox)
    intersection_area = cv2.countNonZero(intersection)
    
    return float(intersection_area)


def calculate_overlap_ratio(polygon: np.ndarray, bbox: Tuple[int, int, int, int]) -> float:
    """
    Calculate what fraction of the polygon is covered by the bbox.
    
    Returns:
        Overlap ratio in [0, 1]
    """
    poly_area = polygon_area(polygon)
    if poly_area < 1:
        return 0.0
    
    intersection = polygon_bbox_intersection_area(polygon, bbox)
    return intersection / poly_area


# =============================================================================
# Temporal smoothing with hysteresis
# =============================================================================

@dataclass
class SpotState:
    """State for a single parking spot."""
    history: deque = field(default_factory=lambda: deque(maxlen=CONFIG.history_size))
    current_status: bool = False  # False = free, True = occupied
    consecutive_count: int = 0
    last_max_ratio: float = 0.0
    
    def update(self, new_ratio: float) -> bool:
        """
        Update state with new overlap ratio and return final status.
        Uses hysteresis and majority voting.
        """
        self.last_max_ratio = new_ratio
        
        # Determine raw status based on hysteresis
        if self.current_status:
            # Currently occupied - need ratio < threshold_free to become free
            raw_occupied = new_ratio >= CONFIG.threshold_free
        else:
            # Currently free - need ratio >= threshold_occupied to become occupied
            raw_occupied = new_ratio >= CONFIG.threshold_occupied
        
        # Add to history
        self.history.append(raw_occupied)
        
        # Count consecutive same states
        if len(self.history) >= 2:
            if self.history[-1] == self.history[-2]:
                self.consecutive_count += 1
            else:
                self.consecutive_count = 1
        else:
            self.consecutive_count = 1
        
        # Majority voting over history
        if len(self.history) >= CONFIG.min_consecutive_for_change:
            occupied_count = sum(self.history)
            majority_occupied = occupied_count > len(self.history) / 2
            
            # Only change status if we have enough consecutive same states
            if self.consecutive_count >= CONFIG.min_consecutive_for_change:
                self.current_status = majority_occupied
        
        return self.current_status


# =============================================================================
# Main detector class
# =============================================================================

class YOLOParkingDetector:
    """
    Parking spot occupancy detector using YOLOv8.
    """
    
    def __init__(self, model_path: str = 'yolov8n.pt'):
        self.model = None
        self.model_path = model_path
        self._load_model()
        
        # Vehicle class IDs in COCO dataset
        # 2: car, 3: motorcycle, 5: bus, 7: truck
        self.vehicle_classes = [2, 3, 5, 7]
        
        # State for each parking spot
        self.spot_states: Dict[str, SpotState] = {}
        
        # Last frame detections (for debug visualization)
        self.last_detections: List[Tuple[int, int, int, int, float, int]] = []
        self.last_debug_info: Dict[str, Dict] = {}
    
    def _load_model(self):
        """Load YOLO model."""
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_path)
            print(f'[Detector] YOLOv8 model loaded: {self.model_path}')
        except ImportError:
            print('[Detector] ERROR: ultralytics not installed')
            self.model = None
        except Exception as e:
            print(f'[Detector] ERROR loading model: {e}')
            self.model = None
    
    def detect_occupancy(self, frame: np.ndarray, spots: List[Dict[str, Any]]) -> Dict[str, bool]:
        """
        Detect occupancy for each parking spot.
        
        Args:
            frame: BGR image (video frame)
            spots: List of spots with 'id' and 'polygon' keys
            
        Returns:
            Dictionary mapping spot IDs to occupancy status
        """
        if frame is None or len(spots) == 0:
            return {}
        
        if self.model is None:
            return self._fallback_detection(frame, spots)
        
        # Run YOLO detection
        try:
            results = self.model(frame, verbose=False, conf=CONFIG.confidence_threshold)[0]
        except Exception as e:
            print(f'[Detector] YOLO error: {e}')
            return self._fallback_detection(frame, spots)
        
        # Extract vehicle bounding boxes
        vehicle_boxes = []
        for box in results.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            
            if cls_id in self.vehicle_classes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                vehicle_boxes.append((x1, y1, x2, y2, conf, cls_id))
        
        self.last_detections = vehicle_boxes
        
        if CONFIG.debug_enabled:
            print(f'[Detector] Found {len(vehicle_boxes)} vehicles')
        
        # Process each parking spot
        occupancy_map = {}
        self.last_debug_info = {}
        
        for spot in spots:
            spot_id = spot.get('id')
            polygon_data = spot.get('polygon', [])
            
            if not spot_id or len(polygon_data) < 3:
                continue
            
            # Convert polygon to numpy array
            polygon = np.array([[int(p['x']), int(p['y'])] for p in polygon_data], dtype=np.int32)
            poly_area = polygon_area(polygon)
            
            if poly_area < 100:
                occupancy_map[spot_id] = False
                continue
            
            # Initialize spot state if needed
            if spot_id not in self.spot_states:
                self.spot_states[spot_id] = SpotState()
            
            # Find maximum overlap with any vehicle
            max_ratio = 0.0
            best_bbox = None
            
            for (x1, y1, x2, y2, conf, cls_id) in vehicle_boxes:
                ratio = calculate_overlap_ratio(polygon, (x1, y1, x2, y2))
                if ratio > max_ratio:
                    max_ratio = ratio
                    best_bbox = (x1, y1, x2, y2)
            
            # Update spot state with smoothing
            is_occupied = self.spot_states[spot_id].update(max_ratio)
            occupancy_map[spot_id] = bool(is_occupied)
            
            # Store debug info (ensure JSON serializable)
            self.last_debug_info[spot_id] = {
                'max_ratio': float(max_ratio),
                'poly_area': float(poly_area),
                'is_occupied': bool(is_occupied),
                'best_bbox': best_bbox,
                'history_len': len(self.spot_states[spot_id].history),
                'consecutive': self.spot_states[spot_id].consecutive_count,
            }
            
            if CONFIG.debug_enabled:
                status = "OCCUPIED" if is_occupied else "FREE"
                print(f'[Detector] {spot_id}: ratio={max_ratio:.3f}, status={status}')
        
        return occupancy_map
    
    def _fallback_detection(self, frame: np.ndarray, spots: List[Dict[str, Any]]) -> Dict[str, bool]:
        """Fallback edge-based detection when YOLO is unavailable."""
        if frame is None or len(spots) == 0:
            return {}
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        
        occupancy_map = {}
        
        for spot in spots:
            spot_id = spot.get('id')
            polygon_data = spot.get('polygon', [])
            
            if not spot_id or len(polygon_data) < 3:
                continue
            
            polygon = np.array([[int(p['x']), int(p['y'])] for p in polygon_data], dtype=np.int32)
            mask = np.zeros(gray.shape, dtype=np.uint8)
            cv2.fillPoly(mask, [polygon], 255)
            
            area = polygon_area(polygon)
            if area < 100:
                occupancy_map[spot_id] = False
                continue
            
            masked_edges = cv2.bitwise_and(edges, edges, mask=mask)
            edge_count = cv2.countNonZero(masked_edges)
            edge_ratio = edge_count / area if area > 0 else 0
            
            if spot_id not in self.spot_states:
                self.spot_states[spot_id] = SpotState()
            
            is_occupied = self.spot_states[spot_id].update(edge_ratio * 2)  # Scale for edge detection
            occupancy_map[spot_id] = bool(is_occupied)
        
        return occupancy_map
    
    def get_debug_info(self) -> Dict[str, Any]:
        """Get debug information for visualization."""
        return {
            'detections': self.last_detections,
            'spots': self.last_debug_info,
            'config': {
                'threshold_occupied': CONFIG.threshold_occupied,
                'threshold_free': CONFIG.threshold_free,
                'history_size': CONFIG.history_size,
            }
        }
    
    def reset(self):
        """Reset all spot states."""
        self.spot_states.clear()
        self.last_detections = []
        self.last_debug_info = {}
    
    @staticmethod
    def set_config(
        threshold_occupied: Optional[float] = None,
        threshold_free: Optional[float] = None,
        history_size: Optional[int] = None,
        debug_enabled: Optional[bool] = None
    ):
        """Update detector configuration."""
        if threshold_occupied is not None:
            CONFIG.threshold_occupied = max(0.05, min(0.95, threshold_occupied))
        if threshold_free is not None:
            CONFIG.threshold_free = max(0.05, min(0.95, threshold_free))
        if history_size is not None:
            CONFIG.history_size = max(1, min(30, history_size))
        if debug_enabled is not None:
            CONFIG.debug_enabled = debug_enabled
        
        print(f'[Detector] Config updated: occupied={CONFIG.threshold_occupied}, '
              f'free={CONFIG.threshold_free}, history={CONFIG.history_size}')


# Alias for backward compatibility
ParkingDetector = YOLOParkingDetector
