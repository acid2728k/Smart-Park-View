import { Point } from '../types';

export function isPointInPolygon(point: Point, polygon: Point[]): boolean {
  if (polygon.length < 3) return false;
  
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i].x;
    const yi = polygon[i].y;
    const xj = polygon[j].x;
    const yj = polygon[j].y;
    
    if (((yi > point.y) !== (yj > point.y)) &&
        (point.x < (xj - xi) * (point.y - yi) / (yj - yi) + xi)) {
      inside = !inside;
    }
  }
  
  return inside;
}

export function getPolygonCenter(polygon: Point[]): Point {
  if (polygon.length === 0) return { x: 0, y: 0 };
  
  const sum = polygon.reduce(
    (acc, p) => ({ x: acc.x + p.x, y: acc.y + p.y }),
    { x: 0, y: 0 }
  );
  
  return {
    x: sum.x / polygon.length,
    y: sum.y / polygon.length,
  };
}

export function scalePolygon(polygon: Point[], scaleX: number, scaleY: number): Point[] {
  return polygon.map(p => ({
    x: p.x * scaleX,
    y: p.y * scaleY,
  }));
}
