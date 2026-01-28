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
}

export interface SpotDebugInfo {
  yoloRatio: number;
  textureScore: number;
  occupied: boolean;
  decision: string;
}

export interface DebugInfo {
  allDetections?: Detection[];
  vehicleBoxes?: Detection[];
  spotInfo: Record<string, SpotDebugInfo>;
}
