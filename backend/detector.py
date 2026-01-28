"""
Parking spot occupancy detector using YOLOv8 + fallback texture analysis.

Features:
- YOLOv8 vehicle detection with letterbox-aware coordinate mapping
- Fallback texture/edge analysis when YOLO misses vehicles
- Hysteresis thresholds to prevent flickering
- Temporal smoothing with majority voting
- Comprehensive debug mode
"""

import cv2
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from collections import deque
from dataclasses import dataclass, field


# =============================================================================
# Configuration
# =============================================================================

# Debug flag - set to True to see all detections
DEBUG_DETECTION = True

@dataclass
class DetectorConfig:
    """Configuration for occupancy detection."""
    # YOLO settings
    confidence_threshold: float = 0.15  # Lower to catch more vehicles
    nms_iou_threshold: float = 0.45
    
    # Hysteresis thresholds for YOLO-based detection
    threshold_occupied: float = 0.12    # Lower threshold for partial overlaps
    threshold_free: float = 0.06
    
    # Fallback texture analysis thresholds - LOWERED for edge cases
    texture_threshold_occupied: float = 18.0  # Was 25, now 18 to catch TEX: 21.9
    texture_threshold_free: float = 12.0
    
    # Combined decision
    use_fallback: bool = True
    
    # Temporal smoothing
    history_size: int = 10
    min_consecutive_for_change: int = 3
    
    # Debug
    debug_enabled: bool = DEBUG_DETECTION
    debug_show_all_detections: bool = True


CONFIG = DetectorConfig()


# =============================================================================
# Geometry utilities
# =============================================================================

def polygon_area(polygon: np.ndarray) -> float:
    """Calculate area using Shoelace formula."""
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
    """Calculate intersection area between polygon and bbox using masks."""
    x1, y1, x2, y2 = bbox
    
    # Ensure valid bbox
    if x2 <= x1 or y2 <= y1:
        return 0.0
    
    # Get polygon bounds
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
    
    # Intersection
    intersection = cv2.bitwise_and(mask_poly, mask_bbox)
    return float(cv2.countNonZero(intersection))


def calculate_overlap_ratio(polygon: np.ndarray, bbox: Tuple[int, int, int, int]) -> float:
    """Calculate fraction of polygon covered by bbox."""
    poly_area = polygon_area(polygon)
    if poly_area < 1:
        return 0.0
    
    intersection = polygon_bbox_intersection_area(polygon, bbox)
    return intersection / poly_area


# =============================================================================
# Texture/Edge analysis
# =============================================================================

def compute_texture_score(frame: np.ndarray, polygon: np.ndarray) -> Tuple[float, Dict]:
    """
    Compute texture score for parking spot region.
    Returns (score, debug_info).
    """
    debug = {'edge_density': 0, 'intensity_std': 0, 'mean_intensity': 0}
    
    if frame is None or len(polygon) < 3:
        return 0.0, debug
    
    # Convert to grayscale
    if len(frame.shape) == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame
    
    # Create polygon mask
    mask = np.zeros(gray.shape, dtype=np.uint8)
    cv2.fillPoly(mask, [polygon], 255)
    
    # Get area
    area = polygon_area(polygon)
    if area < 100:
        return 0.0, debug
    
    # Blur and edge detection
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 30, 100)  # Lower thresholds for more edges
    
    # Masked edge count
    masked_edges = cv2.bitwise_and(edges, edges, mask=mask)
    edge_count = cv2.countNonZero(masked_edges)
    edge_density = (edge_count / area) * 100
    
    # Intensity stats
    masked_gray = cv2.bitwise_and(blurred, blurred, mask=mask)
    pixels = masked_gray[mask > 0]
    
    intensity_std = float(np.std(pixels)) if len(pixels) > 0 else 0
    mean_intensity = float(np.mean(pixels)) if len(pixels) > 0 else 0
    
    # Combined score
    score = edge_density + (intensity_std * 0.5)
    
    debug = {
        'edge_density': round(edge_density, 2),
        'intensity_std': round(intensity_std, 2),
        'mean_intensity': round(mean_intensity, 2),
        'edge_count': edge_count,
        'area': round(area, 0)
    }
    
    return float(score), debug


# =============================================================================
# Spot State with smoothing
# =============================================================================

@dataclass
class SpotState:
    """State for a single parking spot with hysteresis."""
    history: deque = field(default_factory=lambda: deque(maxlen=CONFIG.history_size))
    current_status: bool = False
    consecutive_count: int = 0
    last_yolo_ratio: float = 0.0
    last_texture_score: float = 0.0
    
    def update(self, yolo_ratio: float, texture_score: float) -> bool:
        """Update and return occupancy status."""
        self.last_yolo_ratio = yolo_ratio
        self.last_texture_score = texture_score
        
        # Determine raw status
        if self.current_status:
            # Currently occupied - need BOTH signals low to become free
            yolo_free = yolo_ratio < CONFIG.threshold_free
            texture_free = texture_score < CONFIG.texture_threshold_free
            raw_occupied = not (yolo_free and (not CONFIG.use_fallback or texture_free))
        else:
            # Currently free - EITHER signal can trigger occupied
            yolo_occupied = yolo_ratio >= CONFIG.threshold_occupied
            texture_occupied = CONFIG.use_fallback and texture_score >= CONFIG.texture_threshold_occupied
            raw_occupied = yolo_occupied or texture_occupied
        
        # Add to history
        self.history.append(raw_occupied)
        
        # Count consecutive
        if len(self.history) >= 2:
            if self.history[-1] == self.history[-2]:
                self.consecutive_count += 1
            else:
                self.consecutive_count = 1
        else:
            self.consecutive_count = 1
        
        # Majority voting with consecutive requirement
        if len(self.history) >= CONFIG.min_consecutive_for_change:
            occupied_count = sum(self.history)
            majority_occupied = occupied_count > len(self.history) / 2
            
            if self.consecutive_count >= CONFIG.min_consecutive_for_change:
                self.current_status = majority_occupied
        
        return self.current_status


# =============================================================================
# Main Detector
# =============================================================================

class YOLOParkingDetector:
    """YOLOv8 parking detector with texture fallback."""
    
    # Vehicle classes from COCO
    VEHICLE_CLASSES = {
        2: 'car',
        3: 'motorcycle',
        5: 'bus',
        7: 'truck',
    }
    
    # Classes to ignore (false positives in parking lots)
    IGNORE_CLASSES = {'snowboard', 'skateboard', 'sports ball', 'frisbee', 'kite'}
    
    def __init__(self, model_path: str = 'yolov8n.pt'):
        self.model = None
        self.model_path = model_path
        self._load_model()
        
        self.spot_states: Dict[str, SpotState] = {}
        self.last_raw_detections: List[Dict] = []
        self.last_vehicle_detections: List[Dict] = []
        self.last_debug_info: Dict[str, Dict] = {}
        self.frame_size: Tuple[int, int] = (0, 0)
    
    def _load_model(self):
        """Load YOLO model."""
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_path)
            print(f'[Detector] YOLOv8 loaded: {self.model_path}')
            print(f'[Detector] Conf threshold: {CONFIG.confidence_threshold}')
            print(f'[Detector] Texture threshold: {CONFIG.texture_threshold_occupied}')
        except Exception as e:
            print(f'[Detector] ERROR: {e}')
            self.model = None
    
    def detect_occupancy(self, frame: np.ndarray, spots: List[Dict[str, Any]]) -> Dict[str, bool]:
        """Detect occupancy for each parking spot."""
        if frame is None or len(spots) == 0:
            return {}
        
        self.frame_size = (frame.shape[1], frame.shape[0])  # width, height
        
        # Run YOLO
        raw_detections = []
        vehicle_detections = []
        
        if self.model is not None:
            try:
                # YOLO handles letterbox internally and returns coords in original frame space
                results = self.model(
                    frame,
                    verbose=False,
                    conf=CONFIG.confidence_threshold,
                    iou=CONFIG.nms_iou_threshold
                )[0]
                
                class_names = results.names
                
                for box in results.boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                    cls_name = class_names.get(cls_id, f'cls_{cls_id}')
                    
                    is_vehicle = cls_id in self.VEHICLE_CLASSES
                    is_ignored = cls_name.lower() in self.IGNORE_CLASSES
                    
                    det = {
                        'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
                        'conf': conf,
                        'cls_id': cls_id,
                        'cls_name': cls_name,
                        'is_vehicle': is_vehicle,
                        'is_ignored': is_ignored,
                        'bbox_area': (x2 - x1) * (y2 - y1)
                    }
                    raw_detections.append(det)
                    
                    if is_vehicle and not is_ignored:
                        vehicle_detections.append(det)
                
            except Exception as e:
                print(f'[Detector] YOLO error: {e}')
        
        self.last_raw_detections = raw_detections
        self.last_vehicle_detections = vehicle_detections
        
        if CONFIG.debug_enabled:
            print(f'[Detector] Frame {self.frame_size}, Raw detections: {len(raw_detections)}, Vehicles: {len(vehicle_detections)}')
        
        # Process spots
        occupancy_map = {}
        self.last_debug_info = {}
        
        for spot in spots:
            spot_id = spot.get('id')
            polygon_data = spot.get('polygon', [])
            
            if not spot_id or len(polygon_data) < 3:
                continue
            
            # Polygon in video-space (native coordinates)
            polygon = np.array([[int(p['x']), int(p['y'])] for p in polygon_data], dtype=np.int32)
            poly_area = polygon_area(polygon)
            
            if poly_area < 50:
                occupancy_map[spot_id] = False
                continue
            
            # Initialize state
            if spot_id not in self.spot_states:
                self.spot_states[spot_id] = SpotState()
            
            # Find best vehicle overlap
            max_ratio = 0.0
            best_det = None
            all_overlaps = []
            
            for det in vehicle_detections:
                bbox = (det['x1'], det['y1'], det['x2'], det['y2'])
                ratio = calculate_overlap_ratio(polygon, bbox)
                all_overlaps.append({'det': det['cls_name'], 'conf': det['conf'], 'ratio': ratio})
                
                if ratio > max_ratio:
                    max_ratio = ratio
                    best_det = det
            
            # Compute texture fallback
            texture_score, texture_debug = compute_texture_score(frame, polygon)
            
            # Update state
            is_occupied = self.spot_states[spot_id].update(max_ratio, texture_score)
            occupancy_map[spot_id] = bool(is_occupied)
            
            # Determine decision source
            yolo_triggered = max_ratio >= CONFIG.threshold_occupied
            texture_triggered = texture_score >= CONFIG.texture_threshold_occupied
            
            if yolo_triggered:
                decision = 'YOLO'
            elif texture_triggered:
                decision = 'TEXTURE'
            else:
                decision = 'FREE'
            
            # Store debug info
            self.last_debug_info[spot_id] = {
                'yolo_ratio': float(max_ratio),
                'texture_score': float(texture_score),
                'texture_debug': texture_debug,
                'is_occupied': bool(is_occupied),
                'decision': decision,
                'best_det': {
                    'cls': best_det['cls_name'] if best_det else None,
                    'conf': best_det['conf'] if best_det else 0,
                    'bbox': [best_det['x1'], best_det['y1'], best_det['x2'], best_det['y2']] if best_det else None
                },
                'all_overlaps': all_overlaps,
                'poly_bounds': [int(polygon[:, 0].min()), int(polygon[:, 1].min()),
                               int(polygon[:, 0].max()), int(polygon[:, 1].max())],
                'poly_area': float(poly_area),
                'thresholds': {
                    'yolo_occupied': CONFIG.threshold_occupied,
                    'yolo_free': CONFIG.threshold_free,
                    'texture_occupied': CONFIG.texture_threshold_occupied,
                    'texture_free': CONFIG.texture_threshold_free
                }
            }
            
            if CONFIG.debug_enabled:
                print(f'[Detector] {spot_id}: YOLO={max_ratio:.1%} TEX={texture_score:.1f} -> {decision} ({is_occupied})')
        
        return occupancy_map
    
    def get_debug_info(self) -> Dict[str, Any]:
        """Get comprehensive debug info."""
        return {
            'frame_size': self.frame_size,
            'raw_detections': self.last_raw_detections,
            'vehicle_detections': self.last_vehicle_detections,
            'spots': self.last_debug_info,
            'config': {
                'confidence_threshold': CONFIG.confidence_threshold,
                'threshold_occupied': CONFIG.threshold_occupied,
                'threshold_free': CONFIG.threshold_free,
                'texture_threshold_occupied': CONFIG.texture_threshold_occupied,
                'texture_threshold_free': CONFIG.texture_threshold_free,
                'use_fallback': CONFIG.use_fallback,
                'history_size': CONFIG.history_size,
            }
        }
    
    def reset(self):
        """Reset states."""
        self.spot_states.clear()
        self.last_raw_detections = []
        self.last_vehicle_detections = []
        self.last_debug_info = {}
    
    @staticmethod
    def set_config(**kwargs):
        """Update configuration."""
        for key, value in kwargs.items():
            if hasattr(CONFIG, key) and value is not None:
                setattr(CONFIG, key, value)
                print(f'[Detector] {key} = {value}')


ParkingDetector = YOLOParkingDetector
