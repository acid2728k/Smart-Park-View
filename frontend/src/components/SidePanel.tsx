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
          <button className="btn-icon" onClick={onToggleHide} title="Hide panel">
            {isHidden ? <Eye size={18} /> : <EyeOff size={18} />}
          </button>
          <button className="btn-icon" onClick={onToggleFullscreen} title="Fullscreen">
            <Maximize2 size={18} />
          </button>
        </div>
      </div>

      <div className="side-panel-content">
        <div className="stats-grid">
          <div className="stat-card free">
            <div className="stat-value">{stats.free}</div>
            <div className="stat-label">Free</div>
          </div>
          <div className="stat-card occupied">
            <div className="stat-value">{stats.occupied}</div>
            <div className="stat-label">Occupied</div>
          </div>
        </div>

        <div className="spots-section">
          <h3>Parking Spots ({stats.total})</h3>
          <div className="spots-list">
            {spots.map((spot) => (
              <div key={spot.id} className="spot-item">
                <div className={`spot-indicator ${spot.isOccupied ? 'occupied' : 'free'}`} />
                <span className="spot-name">{spot.name}</span>
                <span className="spot-status">
                  {spot.isOccupied ? 'Occupied' : 'Free'}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div style={{ marginTop: '24px' }}>
          <button className="btn btn-secondary btn-full" onClick={onReset}>
            <RotateCcw size={16} />
            New Calibration
          </button>
        </div>
      </div>
    </div>
  );
}
