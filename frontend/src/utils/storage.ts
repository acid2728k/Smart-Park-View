import { ParkingConfig, ParkingSpot } from '../types';

const STORAGE_KEY = 'smart-park-view-config';

export function saveConfig(config: ParkingConfig): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
}

export function loadConfig(): ParkingConfig | null {
  const data = localStorage.getItem(STORAGE_KEY);
  if (!data) return null;
  try {
    return JSON.parse(data) as ParkingConfig;
  } catch {
    return null;
  }
}

export function clearConfig(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export function updateSpotOccupancy(spots: ParkingSpot[], occupancyMap: Record<string, boolean>): ParkingSpot[] {
  return spots.map(spot => ({
    ...spot,
    isOccupied: occupancyMap[spot.id] ?? spot.isOccupied,
  }));
}
