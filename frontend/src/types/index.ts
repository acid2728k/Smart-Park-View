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

export interface VehicleBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  conf: number;
}

export interface SpotDebugInfo {
  ratio: number;
  occupied: boolean;
}

export interface DebugInfo {
  vehicleBoxes: VehicleBox[];
  spotInfo: Record<string, SpotDebugInfo>;
}
