import React from 'react';
import { Minimize2, Eye, EyeOff } from 'lucide-react';
import { ParkingStats } from '../types';

interface FullscreenHUDProps {
  stats: ParkingStats;
  isUiHidden: boolean;
  onExitFullscreen: () => void;
  onToggleUi: () => void;
}

export function FullscreenHUD({
  stats,
  isUiHidden,
  onExitFullscreen,
  onToggleUi,
}: FullscreenHUDProps) {
  return (
    <div className="fullscreen-hud">
      {/* Stats popup */}
      <div className="fullscreen-stats">
        <div className="fullscreen-stat free">
          <span className="fullscreen-stat-value">{stats.free}</span>
          <span className="fullscreen-stat-label">Свободно</span>
        </div>
        <div className="fullscreen-stat-divider" />
        <div className="fullscreen-stat occupied">
          <span className="fullscreen-stat-value">{stats.occupied}</span>
          <span className="fullscreen-stat-label">Занято</span>
        </div>
      </div>

      {/* Control buttons */}
      <div className="fullscreen-controls">
        <button
          className="fullscreen-btn"
          onClick={onToggleUi}
          title={isUiHidden ? 'Показать UI' : 'Скрыть UI'}
        >
          {isUiHidden ? <Eye size={20} /> : <EyeOff size={20} />}
        </button>
        <button
          className="fullscreen-btn"
          onClick={onExitFullscreen}
          title="Выйти из полноэкранного режима"
        >
          <Minimize2 size={20} />
        </button>
      </div>
    </div>
  );
}
