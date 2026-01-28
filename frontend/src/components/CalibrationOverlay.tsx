import React from 'react';
import { Check, RotateCcw, X } from 'lucide-react';

interface CalibrationOverlayProps {
  currentSpotIndex: number;
  totalSpots: number;
  pointsDrawn: number;
  onConfirmSpot: () => void;
  onUndoPoint: () => void;
  onSkipSpot: () => void;
  onFinishCalibration: () => void;
}

export function CalibrationOverlay({
  currentSpotIndex,
  totalSpots,
  pointsDrawn,
  onConfirmSpot,
  onUndoPoint,
  onSkipSpot,
  onFinishCalibration,
}: CalibrationOverlayProps) {
  const isLastSpot = currentSpotIndex >= totalSpots;
  const canConfirm = pointsDrawn >= 3;

  return (
    <div className="calibration-overlay">
      <div className="calibration-info">
        {isLastSpot ? (
          <>
            <h3>Calibration Complete!</h3>
            <p>All {totalSpots} parking spots have been configured.</p>
            <div className="calibration-actions">
              <button className="btn btn-primary" onClick={onFinishCalibration}>
                <Check size={18} />
                Start Monitoring
              </button>
            </div>
          </>
        ) : (
          <>
            <h3>Draw area for Spot #{currentSpotIndex + 1}</h3>
            <p>
              Click on the corners of the parking spot to define its boundaries.
              Minimum 3 points. Points drawn: {pointsDrawn}
            </p>
            <div className="calibration-actions">
              <button
                className="btn btn-secondary"
                onClick={onUndoPoint}
                disabled={pointsDrawn === 0}
              >
                <RotateCcw size={18} />
                Undo Point
              </button>
              <button
                className="btn btn-secondary"
                onClick={onSkipSpot}
              >
                <X size={18} />
                Skip
              </button>
              <button
                className="btn btn-primary"
                onClick={onConfirmSpot}
                disabled={!canConfirm}
              >
                <Check size={18} />
                Confirm Spot
              </button>
            </div>
            <p style={{ marginTop: '12px', fontSize: '12px', opacity: 0.7 }}>
              Spot {currentSpotIndex + 1} of {totalSpots}
            </p>
          </>
        )}
      </div>
    </div>
  );
}
