import React from 'react';
import { Minimize2 } from 'lucide-react';
import { ParkingStats } from '../types';

interface FullscreenHUDProps {
  stats: ParkingStats;
  onExitFullscreen: () => void;
}

export function FullscreenHUD({
  stats,
  onExitFullscreen,
}: FullscreenHUDProps) {
  return (
    <div className="fullscreen-hud">
      {/* Stats popup */}
      <div className="fullscreen-stats">
        <div className="fullscreen-stat free">
          <span className="fullscreen-stat-value">{stats.free}</span>
          <span className="fullscreen-stat-label">Free</span>
        </div>
        <div className="fullscreen-stat-divider" />
        <div className="fullscreen-stat occupied">
          <span className="fullscreen-stat-value">{stats.occupied}</span>
          <span className="fullscreen-stat-label">Occupied</span>
        </div>
      </div>

      {/* Exit fullscreen button */}
      <div className="fullscreen-controls">
        <button
          className="fullscreen-btn"
          onClick={onExitFullscreen}
          title="Exit fullscreen"
        >
          <Minimize2 size={20} />
        </button>
      </div>
    </div>
  );
}
