"""
Parking spot occupancy detector using YOLOv8 + edge-based fallback.

Features:
- YOLOv8 vehicle detection
- Edge-based fallback for top-view detection (when YOLO fails)
- Smart baseline capture (only when spot appears empty)
- Diff-based detection when baseline is available
- Hysteresis and temporal smoothing
"""

import cv2
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from collections import deque
from dataclasses import dataclass, field


# =============================================================================
# Configuration
# =============================================================================

DEBUG_DETECTION = True

@dataclass
class DetectorConfig:
    """Configuration for occupancy detection."""
    # YOLO settings
    confidence_threshold: float = 0.15
    nms_iou_threshold: float = 0.45
    
    # YOLO hysteresis thresholds
    yolo_threshold_occupied: float = 0.12
    yolo_threshold_free: float = 0.06
    
    # Edge-based detection (primary fallback for top-view)
    edge_density_threshold_occupied: float = 4.5  # % of edges in ROI
    edge_density_threshold_free: float = 2.5
    intensity_std_threshold_occupied: float = 25.0
    intensity_std_threshold_free: float = 15.0
    
    # Diff-based thresholds (when baseline available)
    diff_mean_threshold_occupied: float = 18.0
    diff_mean_threshold_free: float = 10.0
    changed_ratio_threshold_occupied: float = 0.08
    changed_ratio_threshold_free: float = 0.04
    pixel_diff_threshold: float = 18.0
    
    # Use edge detection as fallback
    use_edge_fallback: bool = True
    # Use diff detection when baseline exists
    use_diff_fallback: bool = True
    
    # Baseline settings
    baseline_warmup_frames: int = 5
    baseline_update_alpha: float = 0.01
    baseline_stable_frames: int = 30
    # Only capture baseline when edge density is low (spot looks empty)
    baseline_max_edge_density: float = 3.0
    
    # Temporal smoothing
    history_size: int = 10
    min_consecutive_for_change: int = 3
    
    # Debug
    debug_enabled: bool = DEBUG_DETECTION


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
    
    if x2 <= x1 or y2 <= y1:
        return 0.0
    
    poly_x_min = int(polygon[:, 0].min())
    poly_y_min = int(polygon[:, 1].min())
    poly_x_max = int(polygon[:, 0].max())
    poly_y_max = int(polygon[:, 1].max())
    
    if x2 <= poly_x_min or x1 >= poly_x_max or y2 <= poly_y_min or y1 >= poly_y_max:
        return 0.0
    
    min_x = max(0, min(x1, poly_x_min) - 1)
    min_y = max(0, min(y1, poly_y_min) - 1)
    max_x = max(x2, poly_x_max) + 2
    max_y = max(y2, poly_y_max) + 2
    
    h = max_y - min_y
    w = max_x - min_x
    
    if h <= 0 or w <= 0:
        return 0.0
    
    local_polygon = polygon.copy().astype(np.int32)
    local_polygon[:, 0] -= min_x
    local_polygon[:, 1] -= min_y
    
    local_bbox = np.array([
        [x1 - min_x, y1 - min_y],
        [x2 - min_x, y1 - min_y],
        [x2 - min_x, y2 - min_y],
        [x1 - min_x, y2 - min_y]
    ], dtype=np.int32)
    
    mask_poly = np.zeros((h, w), dtype=np.uint8)
    mask_bbox = np.zeros((h, w), dtype=np.uint8)
    
    cv2.fillPoly(mask_poly, [local_polygon], 255)
    cv2.fillPoly(mask_bbox, [local_bbox], 255)
    
    intersection = cv2.bitwise_and(mask_poly, mask_bbox)
    return float(cv2.countNonZero(intersection))


def calculate_overlap_ratio(polygon: np.ndarray, bbox: Tuple[int, int, int, int]) -> float:
    """Calculate fraction of polygon covered by bbox."""
    poly_area = polygon_area(polygon)
    if poly_area < 1:
        return 0.0
    
    intersection = polygon_bbox_intersection_area(polygon, bbox)
    return intersection / poly_area


def create_polygon_mask(frame_shape: Tuple[int, ...], polygon: np.ndarray) -> np.ndarray:
    """Create binary mask for polygon region."""
    mask = np.zeros(frame_shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [polygon.astype(np.int32)], 255)
    return mask


# =============================================================================
# Edge and texture analysis
# =============================================================================

def compute_edge_metrics(frame: np.ndarray, polygon: np.ndarray, mask: Optional[np.ndarray] = None) -> Dict:
    """
    Compute edge density and intensity stats for parking spot.
    This works regardless of baseline - detects presence of objects by texture.
    """
    result = {
        'edge_density': 0.0,
        'intensity_std': 0.0,
        'mean_intensity': 0.0,
        'edge_count': 0,
        'pixel_count': 0,
    }
    
    if frame is None or len(polygon) < 3:
        return result
    
    # Convert to grayscale
    if len(frame.shape) == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame.copy()
    
    # Create mask if not provided
    if mask is None:
        mask = create_polygon_mask(gray.shape, polygon)
    
    pixel_count = cv2.countNonZero(mask)
    if pixel_count < 100:
        return result
    
    # Blur and edge detection
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 40, 120)
    
    # Count edges in masked region
    masked_edges = cv2.bitwise_and(edges, edges, mask=mask)
    edge_count = cv2.countNonZero(masked_edges)
    edge_density = (edge_count / pixel_count) * 100
    
    # Intensity statistics
    pixels = blurred[mask > 0]
    intensity_std = float(np.std(pixels)) if len(pixels) > 0 else 0
    mean_intensity = float(np.mean(pixels)) if len(pixels) > 0 else 0
    
    return {
        'edge_density': round(edge_density, 2),
        'intensity_std': round(intensity_std, 2),
        'mean_intensity': round(mean_intensity, 2),
        'edge_count': edge_count,
        'pixel_count': pixel_count,
    }


def compute_diff_metrics(
    current_gray: np.ndarray,
    baseline_gray: np.ndarray,
    mask: np.ndarray
) -> Dict:
    """
    Compute difference metrics between current frame and baseline.
    """
    result = {
        'diff_mean': 0.0,
        'changed_ratio': 0.0,
        'changed_count': 0,
    }
    
    if current_gray is None or baseline_gray is None or mask is None:
        return result
    
    pixel_count = cv2.countNonZero(mask)
    if pixel_count < 100:
        return result
    
    # Blur both for noise reduction
    curr_blur = cv2.GaussianBlur(current_gray, (5, 5), 0).astype(np.float32)
    base_blur = cv2.GaussianBlur(baseline_gray, (5, 5), 0).astype(np.float32)
    
    # Normalize brightness (subtract mean within mask)
    curr_pixels = curr_blur[mask > 0]
    base_pixels = base_blur[mask > 0]
    
    curr_mean = np.mean(curr_pixels)
    base_mean = np.mean(base_pixels)
    
    # Create normalized versions
    curr_norm = curr_blur - curr_mean
    base_norm = base_blur - base_mean
    
    # Compute absolute difference
    diff = np.abs(curr_norm - base_norm)
    diff_values = diff[mask > 0]
    
    diff_mean = float(np.mean(diff_values))
    
    # Binary change mask
    changed = diff > CONFIG.pixel_diff_threshold
    changed_count = np.sum(changed & (mask > 0))
    changed_ratio = float(changed_count) / float(pixel_count)
    
    return {
        'diff_mean': round(diff_mean, 2),
        'changed_ratio': round(changed_ratio, 4),
        'changed_count': int(changed_count),
    }


# =============================================================================
# Spot State
# =============================================================================

@dataclass
class SpotBaseline:
    """Baseline data for a parking spot."""
    gray: Optional[np.ndarray] = None
    mask: Optional[np.ndarray] = None
    is_valid: bool = False
    capture_frame: int = 0
    warmup_count: int = 0
    accumulator: Optional[np.ndarray] = None


@dataclass
class SpotState:
    """State for a single parking spot."""
    history: deque = field(default_factory=lambda: deque(maxlen=CONFIG.history_size))
    current_status: bool = False
    consecutive_free_count: int = 0
    baseline: SpotBaseline = field(default_factory=SpotBaseline)
    
    # Last computed values for debug
    last_yolo_ratio: float = 0.0
    last_edge_density: float = 0.0
    last_intensity_std: float = 0.0
    last_diff_mean: float = 0.0
    last_changed_ratio: float = 0.0
    
    def update(self, raw_occupied: bool) -> bool:
        """Update state with new raw detection result."""
        self.history.append(raw_occupied)
        
        if not raw_occupied:
            self.consecutive_free_count += 1
        else:
            self.consecutive_free_count = 0
        
        # Majority voting with consecutive requirement
        if len(self.history) >= CONFIG.min_consecutive_for_change:
            occupied_count = sum(self.history)
            majority_occupied = occupied_count > len(self.history) / 2
            
            # Check consecutive at end of history
            consecutive = 1
            for i in range(len(self.history) - 2, -1, -1):
                if self.history[i] == self.history[-1]:
                    consecutive += 1
                else:
                    break
            
            if consecutive >= CONFIG.min_consecutive_for_change:
                self.current_status = majority_occupied
        
        return self.current_status


# =============================================================================
# Main Detector
# =============================================================================

class YOLOParkingDetector:
    """YOLOv8 parking detector with edge-based fallback."""
    
    VEHICLE_CLASSES = {2: 'car', 3: 'motorcycle', 5: 'bus', 7: 'truck'}
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
        self.frame_counter: int = 0
    
    def _load_model(self):
        """Load YOLO model."""
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_path)
            print(f'[Detector] YOLOv8 loaded: {self.model_path}')
            print(f'[Detector] Edge thresholds: occ={CONFIG.edge_density_threshold_occupied}, free={CONFIG.edge_density_threshold_free}')
        except Exception as e:
            print(f'[Detector] ERROR: {e}')
            self.model = None
    
    def _try_capture_baseline(self, state: SpotState, gray: np.ndarray, polygon: np.ndarray, edge_density: float):
        """Try to capture baseline if conditions are right."""
        baseline = state.baseline
        
        # Create mask if needed
        if baseline.mask is None:
            baseline.mask = create_polygon_mask(gray.shape, polygon)
        
        # Only capture baseline when edge density is LOW (spot looks empty)
        if edge_density > CONFIG.baseline_max_edge_density:
            # Spot doesn't look empty, don't capture baseline
            baseline.warmup_count = 0
            baseline.accumulator = None
            return
        
        # Accumulate frames for averaging
        if baseline.accumulator is None:
            baseline.accumulator = np.zeros(gray.shape, dtype=np.float64)
            baseline.warmup_count = 0
        
        baseline.accumulator += gray.astype(np.float64)
        baseline.warmup_count += 1
        
        if baseline.warmup_count >= CONFIG.baseline_warmup_frames:
            # Capture averaged baseline
            baseline.gray = (baseline.accumulator / baseline.warmup_count).astype(np.uint8)
            baseline.is_valid = True
            baseline.capture_frame = self.frame_counter
            baseline.accumulator = None
            
            if CONFIG.debug_enabled:
                print(f'[Detector] Baseline captured at frame {self.frame_counter} (edge_density={edge_density:.2f})')
    
    def _update_baseline_adaptive(self, state: SpotState, gray: np.ndarray):
        """Slowly update baseline when spot is stably free."""
        baseline = state.baseline
        if not baseline.is_valid or baseline.gray is None or baseline.mask is None:
            return
        
        alpha = CONFIG.baseline_update_alpha
        baseline.gray = cv2.addWeighted(
            baseline.gray, 1 - alpha,
            gray, alpha, 0
        )
    
    def detect_occupancy(self, frame: np.ndarray, spots: List[Dict[str, Any]]) -> Dict[str, bool]:
        """Detect occupancy for each parking spot."""
        if frame is None or len(spots) == 0:
            return {}
        
        self.frame_counter += 1
        self.frame_size = (frame.shape[1], frame.shape[0])
        
        # Convert to grayscale once
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        
        # Run YOLO
        raw_detections = []
        vehicle_detections = []
        
        if self.model is not None:
            try:
                results = self.model(
                    frame, verbose=False,
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
                        'conf': conf, 'cls_id': cls_id, 'cls_name': cls_name,
                        'is_vehicle': is_vehicle, 'is_ignored': is_ignored,
                    }
                    raw_detections.append(det)
                    
                    if is_vehicle and not is_ignored:
                        vehicle_detections.append(det)
                
            except Exception as e:
                print(f'[Detector] YOLO error: {e}')
        
        self.last_raw_detections = raw_detections
        self.last_vehicle_detections = vehicle_detections
        
        # Process each spot
        occupancy_map = {}
        self.last_debug_info = {}
        
        for spot in spots:
            spot_id = spot.get('id')
            polygon_data = spot.get('polygon', [])
            
            if not spot_id or len(polygon_data) < 3:
                continue
            
            polygon = np.array([[int(p['x']), int(p['y'])] for p in polygon_data], dtype=np.int32)
            poly_area = polygon_area(polygon)
            
            if poly_area < 50:
                occupancy_map[spot_id] = False
                continue
            
            # Initialize state
            if spot_id not in self.spot_states:
                self.spot_states[spot_id] = SpotState()
            
            state = self.spot_states[spot_id]
            
            # Create mask
            if state.baseline.mask is None:
                state.baseline.mask = create_polygon_mask(gray.shape, polygon)
            mask = state.baseline.mask
            
            # === YOLO Detection ===
            max_ratio = 0.0
            best_det = None
            
            for det in vehicle_detections:
                bbox = (det['x1'], det['y1'], det['x2'], det['y2'])
                ratio = calculate_overlap_ratio(polygon, bbox)
                if ratio > max_ratio:
                    max_ratio = ratio
                    best_det = det
            
            state.last_yolo_ratio = max_ratio
            
            # === Edge-based Analysis (always computed) ===
            edge_metrics = compute_edge_metrics(frame, polygon, mask)
            edge_density = edge_metrics['edge_density']
            intensity_std = edge_metrics['intensity_std']
            
            state.last_edge_density = edge_density
            state.last_intensity_std = intensity_std
            
            # === Diff-based Analysis (if baseline exists) ===
            diff_mean = 0.0
            changed_ratio = 0.0
            
            if state.baseline.is_valid and state.baseline.gray is not None:
                diff_metrics = compute_diff_metrics(gray, state.baseline.gray, mask)
                diff_mean = diff_metrics['diff_mean']
                changed_ratio = diff_metrics['changed_ratio']
            
            state.last_diff_mean = diff_mean
            state.last_changed_ratio = changed_ratio
            
            # === Decision Logic ===
            decision = 'FREE'
            raw_occupied = False
            
            # Priority 1: YOLO detection
            if max_ratio >= CONFIG.yolo_threshold_occupied:
                raw_occupied = True
                decision = 'YOLO'
            elif max_ratio > CONFIG.yolo_threshold_free:
                # YOLO uncertain - maintain state
                raw_occupied = state.current_status
                decision = 'YOLO_UNCERTAIN'
            else:
                # Priority 2: Edge-based detection (works without baseline)
                if CONFIG.use_edge_fallback:
                    if state.current_status:
                        # Currently occupied - check if still occupied
                        edge_free = (edge_density < CONFIG.edge_density_threshold_free and 
                                    intensity_std < CONFIG.intensity_std_threshold_free)
                        if edge_free:
                            raw_occupied = False
                            decision = 'EDGE_FREE'
                        else:
                            raw_occupied = True
                            decision = 'EDGE_HOLD'
                    else:
                        # Currently free - check if became occupied
                        edge_occupied = (edge_density >= CONFIG.edge_density_threshold_occupied or
                                        intensity_std >= CONFIG.intensity_std_threshold_occupied)
                        if edge_occupied:
                            raw_occupied = True
                            decision = 'EDGE_OCC'
                        else:
                            raw_occupied = False
                            decision = 'FREE'
                
                # Priority 3: Diff-based (if baseline valid and edge is uncertain)
                if CONFIG.use_diff_fallback and state.baseline.is_valid and decision == 'FREE':
                    if state.current_status:
                        diff_free = (diff_mean < CONFIG.diff_mean_threshold_free and
                                    changed_ratio < CONFIG.changed_ratio_threshold_free)
                        if not diff_free:
                            raw_occupied = True
                            decision = 'DIFF_HOLD'
                    else:
                        diff_occupied = (diff_mean >= CONFIG.diff_mean_threshold_occupied and
                                        changed_ratio >= CONFIG.changed_ratio_threshold_occupied)
                        if diff_occupied:
                            raw_occupied = True
                            decision = 'DIFF_OCC'
            
            # Update state with smoothing
            is_occupied = state.update(raw_occupied)
            occupancy_map[spot_id] = bool(is_occupied)
            
            # Baseline management
            if not state.baseline.is_valid:
                # Try to capture baseline when spot looks empty
                self._try_capture_baseline(state, gray, polygon, edge_density)
            elif state.consecutive_free_count >= CONFIG.baseline_stable_frames:
                # Auto-update baseline when stably free
                self._update_baseline_adaptive(state, gray)
            
            # Store debug info
            self.last_debug_info[spot_id] = {
                'yolo_ratio': float(max_ratio),
                'edge_density': float(edge_density),
                'intensity_std': float(intensity_std),
                'diff_mean': float(diff_mean),
                'changed_ratio': float(changed_ratio),
                'is_occupied': bool(is_occupied),
                'decision': decision,
                'baseline_valid': state.baseline.is_valid,
                'baseline_age': self.frame_counter - state.baseline.capture_frame if state.baseline.is_valid else -1,
                'consecutive_free': state.consecutive_free_count,
                'best_det': {
                    'cls': best_det['cls_name'] if best_det else None,
                    'conf': best_det['conf'] if best_det else 0,
                    'bbox': [best_det['x1'], best_det['y1'], best_det['x2'], best_det['y2']] if best_det else None
                },
                'poly_area': float(poly_area),
                'thresholds': {
                    'yolo_occupied': CONFIG.yolo_threshold_occupied,
                    'edge_density_occupied': CONFIG.edge_density_threshold_occupied,
                    'intensity_std_occupied': CONFIG.intensity_std_threshold_occupied,
                    'diff_mean_occupied': CONFIG.diff_mean_threshold_occupied,
                }
            }
            
            if CONFIG.debug_enabled and self.frame_counter % 30 == 0:
                print(f'[{spot_id}] YOLO={max_ratio:.1%} EDGE={edge_density:.1f}/{intensity_std:.1f} DIFF={diff_mean:.1f}/{changed_ratio:.1%} -> {decision}')
        
        return occupancy_map
    
    def get_debug_info(self) -> Dict[str, Any]:
        """Get debug info for frontend."""
        return {
            'frame_size': self.frame_size,
            'frame_number': self.frame_counter,
            'raw_detections': self.last_raw_detections,
            'vehicle_detections': self.last_vehicle_detections,
            'spots': self.last_debug_info,
            'config': {
                'confidence_threshold': CONFIG.confidence_threshold,
                'yolo_threshold_occupied': CONFIG.yolo_threshold_occupied,
                'edge_density_threshold_occupied': CONFIG.edge_density_threshold_occupied,
                'intensity_std_threshold_occupied': CONFIG.intensity_std_threshold_occupied,
                'diff_mean_threshold_occupied': CONFIG.diff_mean_threshold_occupied,
            }
        }
    
    def reset(self):
        """Reset all states."""
        self.spot_states.clear()
        self.last_raw_detections = []
        self.last_vehicle_detections = []
        self.last_debug_info = {}
        self.frame_counter = 0
        print('[Detector] Reset complete')
    
    @staticmethod
    def set_config(**kwargs):
        """Update configuration."""
        for key, value in kwargs.items():
            if hasattr(CONFIG, key) and value is not None:
                setattr(CONFIG, key, value)
                print(f'[Detector] {key} = {value}')


ParkingDetector = YOLOParkingDetector
