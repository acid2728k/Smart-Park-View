import React, { useRef, useEffect, useCallback, forwardRef, useImperativeHandle, useState } from 'react';
import { ParkingSpot, Point, DebugInfo } from '../types';
import { getPolygonCenter } from '../utils/geometry';

interface VideoPlayerProps {
  videoUrl: string;
  spots: ParkingSpot[];
  isCalibrating: boolean;
  currentPolygon: Point[];
  debugInfo?: DebugInfo | null;
  showDebug?: boolean;
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
  debugInfo,
  showDebug = true,
  onCanvasClick,
  onVideoLoaded,
}, ref) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isVideoReady, setIsVideoReady] = useState(false);

  useImperativeHandle(ref, () => ({
    getVideoElement: () => videoRef.current,
    getCanvasElement: () => canvasRef.current,
  }));

  const updateCanvasSize = useCallback(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!video || !canvas || !container || !video.videoWidth) return;

    // Set canvas internal size to match video resolution
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    
    // Get the actual rendered size of the video
    const videoRect = video.getBoundingClientRect();
    
    // Set canvas display size to match video element rendered size
    canvas.style.width = `${videoRect.width}px`;
    canvas.style.height = `${videoRect.height}px`;
    
    // Position canvas exactly over the video
    canvas.style.position = 'absolute';
    canvas.style.top = '50%';
    canvas.style.left = '50%';
    canvas.style.transform = 'translate(-50%, -50%)';
  }, []);

  const drawOverlay = useCallback(() => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video || !canvas.width) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw ALL detections (debug mode)
    if (showDebug && debugInfo?.allDetections) {
      debugInfo.allDetections.forEach((det) => {
        const isVehicle = det.isVehicle;
        const color = isVehicle ? '#00ffff' : '#ff00ff80';
        
        ctx.strokeStyle = color;
        ctx.lineWidth = isVehicle ? 2 : 1;
        ctx.setLineDash(isVehicle ? [] : [4, 4]);
        ctx.strokeRect(det.x1, det.y1, det.x2 - det.x1, det.y2 - det.y1);
        ctx.setLineDash([]);
        
        // Label
        const label = `${det.cls} ${(det.conf * 100).toFixed(0)}%`;
        ctx.font = 'bold 11px sans-serif';
        const textWidth = ctx.measureText(label).width;
        
        // Background for label
        ctx.fillStyle = isVehicle ? 'rgba(0, 255, 255, 0.8)' : 'rgba(255, 0, 255, 0.5)';
        ctx.fillRect(det.x1, det.y1 - 16, textWidth + 6, 16);
        
        // Text
        ctx.fillStyle = '#000';
        ctx.fillText(label, det.x1 + 3, det.y1 - 4);
      });
    }

    // Draw parking spots
    spots.forEach((spot) => {
      if (spot.polygon.length < 3) return;

      const color = spot.isOccupied ? '#ef4444' : '#22c55e';
      
      // Draw polygon fill
      ctx.beginPath();
      ctx.moveTo(spot.polygon[0].x, spot.polygon[0].y);
      spot.polygon.forEach((point, i) => {
        if (i > 0) ctx.lineTo(point.x, point.y);
      });
      ctx.closePath();

      ctx.fillStyle = `${color}33`;
      ctx.fill();

      ctx.strokeStyle = color;
      ctx.lineWidth = 3;
      ctx.stroke();

      // Get debug info for this spot
      const spotDebug = debugInfo?.spotInfo?.[spot.id];
      const center = getPolygonCenter(spot.polygon);
      
      // Calculate label content
      const hasDebug = showDebug && spotDebug;
      const labelText = spot.name;
      
      ctx.font = 'bold 14px sans-serif';
      const labelWidth = Math.max(
        ctx.measureText(labelText).width,
        hasDebug ? 80 : 0
      );
      
      // Label height based on debug info
      const labelHeight = hasDebug ? 52 : 22;
      
      // Draw label background
      ctx.fillStyle = 'rgba(0, 0, 0, 0.85)';
      ctx.fillRect(center.x - labelWidth / 2 - 6, center.y - labelHeight / 2, labelWidth + 12, labelHeight);
      
      // Draw spot name
      ctx.fillStyle = color;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      const nameY = hasDebug ? center.y - 15 : center.y;
      ctx.fillText(labelText, center.x, nameY);
      
      // Draw debug info
      if (hasDebug && spotDebug) {
        // YOLO ratio
        const yoloText = `YOLO: ${(spotDebug.yoloRatio * 100).toFixed(1)}%`;
        ctx.font = 'bold 10px sans-serif';
        ctx.fillStyle = spotDebug.yoloRatio >= 0.15 ? '#fbbf24' : '#9ca3af';
        ctx.fillText(yoloText, center.x, center.y + 1);
        
        // Texture score
        const textureText = `TEX: ${spotDebug.textureScore.toFixed(1)}`;
        ctx.fillStyle = spotDebug.textureScore >= 25 ? '#fbbf24' : '#9ca3af';
        ctx.fillText(textureText, center.x, center.y + 14);
        
        // Decision indicator
        ctx.font = 'bold 9px sans-serif';
        ctx.fillStyle = spotDebug.decision === 'YOLO' ? '#00ffff' : 
                        spotDebug.decision === 'TEXTURE' ? '#ff9500' : '#666';
        ctx.fillText(`[${spotDebug.decision}]`, center.x, center.y - 1 + 14 + 10);
      }
    });

    // Draw current polygon being drawn (calibration mode)
    if (isCalibrating && currentPolygon.length > 0) {
      ctx.beginPath();
      ctx.moveTo(currentPolygon[0].x, currentPolygon[0].y);
      currentPolygon.forEach((point, i) => {
        if (i > 0) ctx.lineTo(point.x, point.y);
      });

      ctx.strokeStyle = '#f59e0b';
      ctx.lineWidth = 3;
      ctx.setLineDash([8, 8]);
      ctx.stroke();
      ctx.setLineDash([]);

      // Draw points
      currentPolygon.forEach((point, index) => {
        ctx.beginPath();
        ctx.arc(point.x, point.y, 8, 0, Math.PI * 2);
        ctx.fillStyle = '#f59e0b';
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.stroke();
        
        // Draw point number
        ctx.fillStyle = '#000';
        ctx.font = 'bold 12px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText((index + 1).toString(), point.x, point.y);
      });
    }
  }, [spots, isCalibrating, currentPolygon, debugInfo, showDebug]);

  // Handle video source change
  useEffect(() => {
    const video = videoRef.current;
    if (!video || !videoUrl) return;

    setIsVideoReady(false);
    video.src = videoUrl;
    video.load();
  }, [videoUrl]);

  // Handle video loaded
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleLoadedMetadata = () => {
      console.log('Video metadata loaded:', video.videoWidth, video.videoHeight);
      setIsVideoReady(true);
      updateCanvasSize();
      onVideoLoaded?.(video.videoWidth, video.videoHeight);
    };

    const handleCanPlay = () => {
      console.log('Video can play');
      video.play().catch(err => console.log('Autoplay prevented:', err));
    };

    const handleError = (e: Event) => {
      console.error('Video error:', e);
    };

    video.addEventListener('loadedmetadata', handleLoadedMetadata);
    video.addEventListener('canplay', handleCanPlay);
    video.addEventListener('error', handleError);
    
    return () => {
      video.removeEventListener('loadedmetadata', handleLoadedMetadata);
      video.removeEventListener('canplay', handleCanPlay);
      video.removeEventListener('error', handleError);
    };
  }, [updateCanvasSize, onVideoLoaded]);

  // Animation loop for continuous redraw
  useEffect(() => {
    if (!isVideoReady) return;

    let animationId: number;

    const animate = () => {
      updateCanvasSize();
      drawOverlay();
      animationId = requestAnimationFrame(animate);
    };

    animationId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationId);
  }, [drawOverlay, updateCanvasSize, isVideoReady]);

  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      updateCanvasSize();
      drawOverlay();
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [updateCanvasSize, drawOverlay]);

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isCalibrating || !onCanvasClick) return;

    const canvas = canvasRef.current;
    if (!canvas || !canvas.width) return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    const point: Point = {
      x: Math.round((e.clientX - rect.left) * scaleX),
      y: Math.round((e.clientY - rect.top) * scaleY),
    };

    console.log('Canvas click:', point);
    onCanvasClick(point);
  };

  return (
    <div className="video-wrapper" ref={containerRef}>
      <video
        ref={videoRef}
        loop
        muted
        playsInline
        autoPlay
      />
      <canvas
        ref={canvasRef}
        className={`video-canvas ${isCalibrating ? 'calibration' : ''}`}
        onClick={handleCanvasClick}
      />
      {!isVideoReady && videoUrl && (
        <div className="video-loading">
          Загрузка видео...
        </div>
      )}
    </div>
  );
});

VideoPlayer.displayName = 'VideoPlayer';
