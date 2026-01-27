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
            <h3>Калибровка завершена!</h3>
            <p>Все {totalSpots} парковочных мест настроены.</p>
            <div className="calibration-actions">
              <button className="btn btn-primary" onClick={onFinishCalibration}>
                <Check size={18} />
                Начать мониторинг
              </button>
            </div>
          </>
        ) : (
          <>
            <h3>Нарисуйте область для места №{currentSpotIndex + 1}</h3>
            <p>
              Кликните по углам парковочного места, чтобы обозначить его границы.
              Минимум 3 точки. Нарисовано точек: {pointsDrawn}
            </p>
            <div className="calibration-actions">
              <button
                className="btn btn-secondary"
                onClick={onUndoPoint}
                disabled={pointsDrawn === 0}
              >
                <RotateCcw size={18} />
                Отменить точку
              </button>
              <button
                className="btn btn-secondary"
                onClick={onSkipSpot}
              >
                <X size={18} />
                Пропустить
              </button>
              <button
                className="btn btn-primary"
                onClick={onConfirmSpot}
                disabled={!canConfirm}
              >
                <Check size={18} />
                Подтвердить место
              </button>
            </div>
            <p style={{ marginTop: '12px', fontSize: '12px', opacity: 0.7 }}>
              Место {currentSpotIndex + 1} из {totalSpots}
            </p>
          </>
        )}
      </div>
    </div>
  );
}
