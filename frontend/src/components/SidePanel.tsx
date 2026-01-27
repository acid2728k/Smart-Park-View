import React from 'react';
import { Car, Eye, EyeOff, Maximize2, RotateCcw } from 'lucide-react';
import { ParkingSpot, ParkingStats } from '../types';

interface SidePanelProps {
  spots: ParkingSpot[];
  stats: ParkingStats;
  isHidden: boolean;
  onToggleHide: () => void;
  onToggleFullscreen: () => void;
  onReset: () => void;
}

export function SidePanel({
  spots,
  stats,
  isHidden,
  onToggleHide,
  onToggleFullscreen,
  onReset,
}: SidePanelProps) {
  return (
    <div className={`side-panel ${isHidden ? 'hidden' : ''}`}>
      <div className="side-panel-header">
        <div className="side-panel-logo">
          <Car size={24} />
          <span>Smart Park View</span>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="btn-icon" onClick={onToggleHide} title="Скрыть панель">
            {isHidden ? <Eye size={18} /> : <EyeOff size={18} />}
          </button>
          <button className="btn-icon" onClick={onToggleFullscreen} title="Полный экран">
            <Maximize2 size={18} />
          </button>
        </div>
      </div>

      <div className="side-panel-content">
        <div className="stats-grid">
          <div className="stat-card free">
            <div className="stat-value">{stats.free}</div>
            <div className="stat-label">Свободно</div>
          </div>
          <div className="stat-card occupied">
            <div className="stat-value">{stats.occupied}</div>
            <div className="stat-label">Занято</div>
          </div>
        </div>

        <div className="spots-section">
          <h3>Парковочные места ({stats.total})</h3>
          <div className="spots-list">
            {spots.map((spot) => (
              <div key={spot.id} className="spot-item">
                <div className={`spot-indicator ${spot.isOccupied ? 'occupied' : 'free'}`} />
                <span className="spot-name">{spot.name}</span>
                <span className="spot-status">
                  {spot.isOccupied ? 'Занято' : 'Свободно'}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div style={{ marginTop: '24px' }}>
          <button className="btn btn-secondary btn-full" onClick={onReset}>
            <RotateCcw size={16} />
            Новая калибровка
          </button>
        </div>
      </div>
    </div>
  );
}
