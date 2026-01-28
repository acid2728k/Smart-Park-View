"""
Parking spot occupancy detector using YOLOv8 + fallback texture analysis.

Features:
- YOLOv8 vehicle detection with extended classes
- Fallback texture/edge analysis when YOLO misses vehicles
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
    # YOLO settings
    confidence_threshold: float = 0.20  # Lower threshold to catch more vehicles
    nms_iou_threshold: float = 0.45     # NMS IoU threshold
    
    # Hysteresis thresholds for YOLO-based detection
    threshold_occupied: float = 0.15    # Become occupied if overlap >= this
    threshold_free: float = 0.08        # Become free if overlap < this
    
    # Fallback texture analysis thresholds
    texture_threshold_occupied: float = 25.0  # Edge density to consider occupied
    texture_threshold_free: float = 15.0      # Edge density to consider free
    
    # Combined decision
    use_fallback: bool = True  # Enable texture fallback
    
    # Temporal smoothing
    history_size: int = 8               # Number of frames to remember
    min_consecutive_for_change: int = 3 # Require N consecutive same states
    
    # Debug
    debug_enabled: bool = True
    debug_show_all_detections: bool = True  # Show all YOLO detections, not just vehicles


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
    """Calculate intersection area between a polygon and a bounding box."""
    x1, y1, x2, y2 = bbox
    
    # Get bounds
    poly_x_min = int(polygon[:, 0].min())
    poly_y_min = int(polygon[:, 1].min())
    poly_x_max = int(polygon[:, 0].max())
    poly_y_max = int(polygon[:, 1].max())
    
    # Quick rejection
    if x2 <= poly_x_min or x1 >= poly_x_max or y2 <= poly_y_min or y1 >= poly_y_max:
        return 0.0
    
    # Create working area
    min_x = max(0, min(x1, poly_x_min) - 1)
    min_y = max(0, min(y1, poly_y_min) - 1)
    max_x = max(x2, poly_x_max) + 2
    max_y = max(y2, poly_y_max) + 2
    
    h = max_y - min_y
    w = max_x - min_x
    
    if h <= 0 or w <= 0:
        return 0.0
    
    # Offset to local space
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
    return float(cv2.countNonZero(intersection))


def calculate_overlap_ratio(polygon: np.ndarray, bbox: Tuple[int, int, int, int]) -> float:
    """Calculate what fraction of the polygon is covered by the bbox."""
    poly_area = polygon_area(polygon)
    if poly_area < 1:
        return 0.0
    
    intersection = polygon_bbox_intersection_area(polygon, bbox)
    return intersection / poly_area


def extract_polygon_roi(frame: np.ndarray, polygon: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Extract ROI from frame using polygon mask.
    Returns (masked_region, mask).
    """
    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [polygon], 255)
    
    # Get bounding rect for efficiency
    x, y, w, h = cv2.boundingRect(polygon)
    
    # Ensure bounds are valid
    x = max(0, x)
    y = max(0, y)
    w = min(w, frame.shape[1] - x)
    h = min(h, frame.shape[0] - y)
    
    if w <= 0 or h <= 0:
        return np.array([]), np.array([])
    
    roi = frame[y:y+h, x:x+w].copy()
    roi_mask = mask[y:y+h, x:x+w]
    
    return roi, roi_mask


# =============================================================================
# Texture/Edge analysis for fallback detection
# =============================================================================

def compute_texture_score(frame: np.ndarray, polygon: np.ndarray) -> float:
    """
    Compute texture/edge density score for a parking spot region.
    Higher score = more likely occupied (cars have more edges/texture).
    """
    if frame is None or len(polygon) < 3:
        return 0.0
    
    # Convert to grayscale
    if len(frame.shape) == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame
    
    # Create polygon mask
    mask = np.zeros(gray.shape, dtype=np.uint8)
    cv2.fillPoly(mask, [polygon], 255)
    
    # Apply Gaussian blur
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Edge detection
    edges = cv2.Canny(blurred, 50, 150)
    
    # Apply mask
    masked_edges = cv2.bitwise_and(edges, edges, mask=mask)
    
    # Calculate edge density
    area = polygon_area(polygon)
    if area < 100:
        return 0.0
    
    edge_count = cv2.countNonZero(masked_edges)
    edge_density = (edge_count / area) * 100  # Percentage
    
    # Also compute intensity variance (cars have varied colors)
    masked_gray = cv2.bitwise_and(blurred, blurred, mask=mask)
    pixels = masked_gray[mask > 0]
    
    if len(pixels) > 0:
        intensity_std = np.std(pixels)
    else:
        intensity_std = 0
    
    # Combined score: edge density + intensity variance contribution
    combined_score = edge_density + (intensity_std * 0.3)
    
    return float(combined_score)


# =============================================================================
# Temporal smoothing with hysteresis
# =============================================================================

@dataclass
class SpotState:
    """State for a single parking spot."""
    history: deque = field(default_factory=lambda: deque(maxlen=CONFIG.history_size))
    current_status: bool = False
    consecutive_count: int = 0
    last_yolo_ratio: float = 0.0
    last_texture_score: float = 0.0
    
    def update(self, yolo_ratio: float, texture_score: float) -> bool:
        """Update state and return final occupancy status."""
        self.last_yolo_ratio = yolo_ratio
        self.last_texture_score = texture_score
        
        # Determine raw status based on hysteresis
        if self.current_status:
            # Currently occupied - check both YOLO and texture
            yolo_free = yolo_ratio < CONFIG.threshold_free
            texture_free = texture_score < CONFIG.texture_threshold_free
            raw_occupied = not (yolo_free and texture_free)
        else:
            # Currently free - either YOLO or texture can trigger occupied
            yolo_occupied = yolo_ratio >= CONFIG.threshold_occupied
            texture_occupied = CONFIG.use_fallback and texture_score >= CONFIG.texture_threshold_occupied
            raw_occupied = yolo_occupied or texture_occupied
        
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
        
        # Majority voting
        if len(self.history) >= CONFIG.min_consecutive_for_change:
            occupied_count = sum(self.history)
            majority_occupied = occupied_count > len(self.history) / 2
            
            if self.consecutive_count >= CONFIG.min_consecutive_for_change:
                self.current_status = majority_occupied
        
        return self.current_status


# =============================================================================
# Main detector class
# =============================================================================

class YOLOParkingDetector:
    """Parking spot occupancy detector using YOLOv8 + texture fallback."""
    
    # Extended vehicle classes from COCO dataset
    # 0: person, 1: bicycle, 2: car, 3: motorcycle, 4: airplane, 5: bus,
    # 6: train, 7: truck, 8: boat
    VEHICLE_CLASSES = {
        2: 'car',
        3: 'motorcycle', 
        5: 'bus',
        7: 'truck',
        # Also include these in case of misclassification
        1: 'bicycle',  # Sometimes motorcycles detected as bicycles
    }
    
    def __init__(self, model_path: str = 'yolov8n.pt'):
        self.model = None
        self.model_path = model_path
        self._load_model()
        
        # State for each parking spot
        self.spot_states: Dict[str, SpotState] = {}
        
        # Last frame detections for debug
        self.last_all_detections: List[Dict] = []  # All YOLO detections
        self.last_vehicle_detections: List[Dict] = []  # Filtered vehicles only
        self.last_debug_info: Dict[str, Dict] = {}
    
    def _load_model(self):
        """Load YOLO model."""
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_path)
            print(f'[Detector] YOLOv8 loaded: {self.model_path}')
            print(f'[Detector] Confidence threshold: {CONFIG.confidence_threshold}')
            print(f'[Detector] Vehicle classes: {list(self.VEHICLE_CLASSES.values())}')
        except ImportError:
            print('[Detector] ERROR: ultralytics not installed')
            self.model = None
        except Exception as e:
            print(f'[Detector] ERROR: {e}')
            self.model = None
    
    def detect_occupancy(self, frame: np.ndarray, spots: List[Dict[str, Any]]) -> Dict[str, bool]:
        """Detect occupancy for each parking spot."""
        if frame is None or len(spots) == 0:
            return {}
        
        # Run YOLO detection
        all_detections = []
        vehicle_boxes = []
        
        if self.model is not None:
            try:
                results = self.model(
                    frame, 
                    verbose=False, 
                    conf=CONFIG.confidence_threshold,
                    iou=CONFIG.nms_iou_threshold
                )[0]
                
                # Get class names
                class_names = results.names
                
                for box in results.boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                    
                    cls_name = class_names.get(cls_id, f'class_{cls_id}')
                    
                    detection = {
                        'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
                        'conf': conf,
                        'cls_id': cls_id,
                        'cls_name': cls_name,
                        'is_vehicle': cls_id in self.VEHICLE_CLASSES
                    }
                    all_detections.append(detection)
                    
                    if cls_id in self.VEHICLE_CLASSES:
                        vehicle_boxes.append((x1, y1, x2, y2, conf, cls_id))
                
            except Exception as e:
                print(f'[Detector] YOLO error: {e}')
        
        self.last_all_detections = all_detections
        self.last_vehicle_detections = [d for d in all_detections if d['is_vehicle']]
        
        if CONFIG.debug_enabled:
            print(f'[Detector] Total detections: {len(all_detections)}, Vehicles: {len(vehicle_boxes)}')
        
        # Process each parking spot
        occupancy_map = {}
        self.last_debug_info = {}
        
        for spot in spots:
            spot_id = spot.get('id')
            polygon_data = spot.get('polygon', [])
            
            if not spot_id or len(polygon_data) < 3:
                continue
            
            polygon = np.array([[int(p['x']), int(p['y'])] for p in polygon_data], dtype=np.int32)
            poly_area = polygon_area(polygon)
            
            if poly_area < 100:
                occupancy_map[spot_id] = False
                continue
            
            # Initialize spot state
            if spot_id not in self.spot_states:
                self.spot_states[spot_id] = SpotState()
            
            # Find maximum overlap with any vehicle
            max_ratio = 0.0
            best_vehicle = None
            
            for (x1, y1, x2, y2, conf, cls_id) in vehicle_boxes:
                ratio = calculate_overlap_ratio(polygon, (x1, y1, x2, y2))
                if ratio > max_ratio:
                    max_ratio = ratio
                    best_vehicle = {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'conf': conf}
            
            # Compute texture fallback score
            texture_score = compute_texture_score(frame, polygon) if CONFIG.use_fallback else 0.0
            
            # Update spot state with both signals
            is_occupied = self.spot_states[spot_id].update(max_ratio, texture_score)
            occupancy_map[spot_id] = bool(is_occupied)
            
            # Store debug info
            self.last_debug_info[spot_id] = {
                'yolo_ratio': float(max_ratio),
                'texture_score': float(texture_score),
                'is_occupied': bool(is_occupied),
                'best_vehicle': best_vehicle,
                'poly_area': float(poly_area),
                'decision': 'YOLO' if max_ratio >= CONFIG.threshold_occupied else ('TEXTURE' if texture_score >= CONFIG.texture_threshold_occupied else 'FREE')
            }
            
            if CONFIG.debug_enabled:
                status = "OCCUPIED" if is_occupied else "FREE"
                decision = self.last_debug_info[spot_id]['decision']
                print(f'[Detector] {spot_id}: yolo={max_ratio:.1%}, texture={texture_score:.1f}, status={status} ({decision})')
        
        return occupancy_map
    
    def get_debug_info(self) -> Dict[str, Any]:
        """Get debug information for visualization."""
        return {
            'all_detections': self.last_all_detections,
            'vehicle_detections': self.last_vehicle_detections,
            'spots': self.last_debug_info,
            'config': {
                'confidence_threshold': CONFIG.confidence_threshold,
                'threshold_occupied': CONFIG.threshold_occupied,
                'threshold_free': CONFIG.threshold_free,
                'texture_threshold_occupied': CONFIG.texture_threshold_occupied,
                'texture_threshold_free': CONFIG.texture_threshold_free,
                'use_fallback': CONFIG.use_fallback,
            }
        }
    
    def reset(self):
        """Reset all spot states."""
        self.spot_states.clear()
        self.last_all_detections = []
        self.last_vehicle_detections = []
        self.last_debug_info = {}
    
    @staticmethod
    def set_config(**kwargs):
        """Update detector configuration."""
        for key, value in kwargs.items():
            if hasattr(CONFIG, key) and value is not None:
                setattr(CONFIG, key, value)
                print(f'[Detector] Config {key} = {value}')


# Alias
ParkingDetector = YOLOParkingDetector
