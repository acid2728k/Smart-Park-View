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
  textureScore: number;
  occupied: boolean;
  decision: string;
  bestDet?: {
    cls: string | null;
    conf: number;
    bbox: number[] | null;
  };
  polyBounds?: number[];
  thresholds?: {
    yolo_occupied: number;
    yolo_free: number;
    texture_occupied: number;
    texture_free: number;
  };
}

export interface DebugInfo {
  frameSize?: number[];
  allDetections?: Detection[];
  vehicleBoxes?: Detection[];
  spotInfo: Record<string, SpotDebugInfo>;
  config?: Record<string, number | boolean>;
}
