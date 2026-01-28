export interface Point {
  x: number;
  y: number;
}

export interface ParkingSpot {
  id: string;
  name: string;
  polygon: Point[];
  isOccupied: boolean;
}

export interface ParkingConfig {
  spots: ParkingSpot[];
  videoSource: string;
  sourceType: 'file' | 'camera' | 'stream';
}

export interface ParkingStats {
  total: number;
  free: number;
  occupied: number;
}

export type AppMode = 'setup' | 'calibration' | 'monitoring';

export interface VideoSource {
  type: 'file' | 'camera' | 'stream';
  url?: string;
  file?: File;
}

// Debug types
export interface Detection {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  conf: number;
  cls: string;
  isVehicle?: boolean;
  isIgnored?: boolean;
}

export interface SpotDebugInfo {
  yoloRatio: number;
  edgeDensity: number;
  intensityStd: number;
  diffMean: number;
  changedRatio: number;
  occupied: boolean;
  decision: string;
  baselineValid?: boolean;
  baselineAge?: number;
  consecutiveFree?: number;
  bestDet?: {
    cls: string | null;
    conf: number;
    bbox: number[] | null;
  };
  thresholds?: {
    yolo_occupied: number;
    edge_density_occupied: number;
    intensity_std_occupied: number;
    diff_mean_occupied: number;
  };
}

export interface DebugInfo {
  frameSize?: number[];
  frameNumber?: number;
  allDetections?: Detection[];
  vehicleBoxes?: Detection[];
  spotInfo: Record<string, SpotDebugInfo>;
  config?: Record<string, number | boolean>;
}
