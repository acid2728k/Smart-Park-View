import React, { useRef, useEffect, useCallback, forwardRef, useImperativeHandle } from 'react';
import { ParkingSpot, Point } from '../types';
import { getPolygonCenter } from '../utils/geometry';

interface VideoPlayerProps {
  videoUrl: string;
  spots: ParkingSpot[];
  isCalibrating: boolean;
  currentPolygon: Point[];
  onCanvasClick?: (point: Point) => void;
  onVideoLoaded?: (width: number, height: number) => void;
}

export interface VideoPlayerRef {
  getVideoElement: () => HTMLVideoElement | null;
  getCanvasElement: () => HTMLCanvasElement | null;
}

export const VideoPlayer = forwardRef<VideoPlayerRef, VideoPlayerProps>(({
  videoUrl,
  spots,
  isCalibrating,
  currentPolygon,
  onCanvasClick,
  onVideoLoaded,
}, ref) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useImperativeHandle(ref, () => ({
    getVideoElement: () => videoRef.current,
    getCanvasElement: () => canvasRef.current,
  }));

  const updateCanvasSize = useCallback(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.style.width = `${video.clientWidth}px`;
    canvas.style.height = `${video.clientHeight}px`;
  }, []);

  const drawOverlay = useCallback(() => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw parking spots
    spots.forEach((spot) => {
      if (spot.polygon.length < 3) return;

      const color = spot.isOccupied ? '#ef4444' : '#22c55e';
      
      ctx.beginPath();
      ctx.moveTo(spot.polygon[0].x, spot.polygon[0].y);
      spot.polygon.forEach((point, i) => {
        if (i > 0) ctx.lineTo(point.x, point.y);
      });
      ctx.closePath();

      ctx.fillStyle = `${color}33`;
      ctx.fill();

      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.stroke();

      // Draw label
      const center = getPolygonCenter(spot.polygon);
      ctx.fillStyle = color;
      ctx.font = 'bold 14px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(spot.name, center.x, center.y);
    });

    // Draw current polygon being drawn (calibration mode)
    if (isCalibrating && currentPolygon.length > 0) {
      ctx.beginPath();
      ctx.moveTo(currentPolygon[0].x, currentPolygon[0].y);
      currentPolygon.forEach((point, i) => {
        if (i > 0) ctx.lineTo(point.x, point.y);
      });

      ctx.strokeStyle = '#f59e0b';
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 5]);
      ctx.stroke();
      ctx.setLineDash([]);

      // Draw points
      currentPolygon.forEach((point) => {
        ctx.beginPath();
        ctx.arc(point.x, point.y, 6, 0, Math.PI * 2);
        ctx.fillStyle = '#f59e0b';
        ctx.fill();
        ctx.strokeStyle = '#000';
        ctx.lineWidth = 2;
        ctx.stroke();
      });
    }
  }, [spots, isCalibrating, currentPolygon]);

  // Handle video loaded
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleLoaded = () => {
      updateCanvasSize();
      onVideoLoaded?.(video.videoWidth, video.videoHeight);
      video.play();
    };

    video.addEventListener('loadedmetadata', handleLoaded);
    return () => video.removeEventListener('loadedmetadata', handleLoaded);
  }, [updateCanvasSize, onVideoLoaded]);

  // Redraw overlay on changes
  useEffect(() => {
    drawOverlay();
  }, [drawOverlay]);

  // Animation loop for continuous redraw
  useEffect(() => {
    let animationId: number;

    const animate = () => {
      drawOverlay();
      animationId = requestAnimationFrame(animate);
    };

    animationId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationId);
  }, [drawOverlay]);

  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      updateCanvasSize();
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [updateCanvasSize]);

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isCalibrating || !onCanvasClick) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    const point: Point = {
      x: (e.clientX - rect.left) * scaleX,
      y: (e.clientY - rect.top) * scaleY,
    };

    onCanvasClick(point);
  };

  return (
    <div className="video-wrapper" ref={containerRef}>
      <video
        ref={videoRef}
        src={videoUrl}
        loop
        muted
        playsInline
      />
      <canvas
        ref={canvasRef}
        className={`video-canvas ${isCalibrating ? 'calibration' : ''}`}
        onClick={handleCanvasClick}
      />
    </div>
  );
});

VideoPlayer.displayName = 'VideoPlayer';
