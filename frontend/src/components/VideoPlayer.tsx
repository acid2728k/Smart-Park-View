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
    if (!video || !canvas || !video.videoWidth) return;

    // Canvas internal size = video native resolution
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    
    // Canvas display size = video rendered size
    const videoRect = video.getBoundingClientRect();
    canvas.style.width = `${videoRect.width}px`;
    canvas.style.height = `${videoRect.height}px`;
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

    // Draw ALL detections (debug)
    if (showDebug && debugInfo?.allDetections) {
      debugInfo.allDetections.forEach((det) => {
        const isVehicle = det.isVehicle;
        const isIgnored = det.isIgnored;
        
        // Color coding: cyan=vehicle, magenta=other, gray=ignored
        let color = '#ff00ff';
        let lineWidth = 1;
        if (isVehicle) {
          color = '#00ffff';
          lineWidth = 2;
        }
        if (isIgnored) {
          color = '#666666';
        }
        
        ctx.strokeStyle = color;
        ctx.lineWidth = lineWidth;
        ctx.setLineDash(isVehicle ? [] : [3, 3]);
        ctx.strokeRect(det.x1, det.y1, det.x2 - det.x1, det.y2 - det.y1);
        ctx.setLineDash([]);
        
        // Label background
        const label = `${det.cls} ${(det.conf * 100).toFixed(0)}%`;
        ctx.font = 'bold 11px monospace';
        const textWidth = ctx.measureText(label).width;
        
        ctx.fillStyle = color + 'cc';
        ctx.fillRect(det.x1, det.y1 - 15, textWidth + 6, 15);
        
        ctx.fillStyle = '#000';
        ctx.fillText(label, det.x1 + 3, det.y1 - 3);
      });
    }

    // Draw parking spots
    spots.forEach((spot) => {
      if (spot.polygon.length < 3) return;

      const color = spot.isOccupied ? '#ef4444' : '#22c55e';
      const spotDebug = debugInfo?.spotInfo?.[spot.id];
      
      // Draw polygon
      ctx.beginPath();
      ctx.moveTo(spot.polygon[0].x, spot.polygon[0].y);
      spot.polygon.forEach((point, i) => {
        if (i > 0) ctx.lineTo(point.x, point.y);
      });
      ctx.closePath();

      ctx.fillStyle = `${color}40`;
      ctx.fill();
      ctx.strokeStyle = color;
      ctx.lineWidth = 3;
      ctx.stroke();

      // Draw best detection bbox if exists (for debugging coordinate alignment)
      if (showDebug && spotDebug?.bestDet?.bbox) {
        const [bx1, by1, bx2, by2] = spotDebug.bestDet.bbox;
        ctx.strokeStyle = '#ffff00';
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 5]);
        ctx.strokeRect(bx1, by1, bx2 - bx1, by2 - by1);
        ctx.setLineDash([]);
      }

      // Label
      const center = getPolygonCenter(spot.polygon);
      const hasDebug = showDebug && spotDebug;
      
      ctx.font = 'bold 13px sans-serif';
      const labelWidth = Math.max(90, ctx.measureText(spot.name).width + 12);
      const labelHeight = hasDebug ? 62 : 24;
      
      // Label background
      ctx.fillStyle = 'rgba(0, 0, 0, 0.9)';
      ctx.fillRect(center.x - labelWidth / 2, center.y - labelHeight / 2, labelWidth, labelHeight);
      
      // Border
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.strokeRect(center.x - labelWidth / 2, center.y - labelHeight / 2, labelWidth, labelHeight);
      
      // Spot name
      ctx.fillStyle = color;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      const nameY = hasDebug ? center.y - 20 : center.y;
      ctx.fillText(spot.name, center.x, nameY);
      
      // Debug info
      if (hasDebug && spotDebug) {
        ctx.font = 'bold 10px monospace';
        
        // YOLO ratio
        const yoloThreshold = spotDebug.thresholds?.yolo_occupied ?? 0.12;
        const yoloTriggered = spotDebug.yoloRatio >= yoloThreshold;
        ctx.fillStyle = yoloTriggered ? '#00ff00' : '#888';
        ctx.fillText(`YOLO: ${(spotDebug.yoloRatio * 100).toFixed(1)}%`, center.x, center.y - 5);
        
        // Edge metrics (edge_density / intensity_std)
        const edgeThreshold = spotDebug.thresholds?.edge_density_occupied ?? 4.5;
        const edgeDensity = spotDebug.edgeDensity ?? 0;
        const intensityStd = spotDebug.intensityStd ?? 0;
        const edgeTriggered = edgeDensity >= edgeThreshold || intensityStd >= 25;
        ctx.fillStyle = edgeTriggered ? '#00ff00' : '#888';
        ctx.fillText(`EDGE: ${edgeDensity.toFixed(1)} / ${intensityStd.toFixed(0)}`, center.x, center.y + 8);
        
        // Decision
        const decisionColor = spotDebug.decision === 'YOLO' ? '#00ffff' : 
                            spotDebug.decision?.includes('EDGE') ? '#ff9500' :
                            spotDebug.decision?.includes('DIFF') ? '#9500ff' : '#666';
        ctx.fillStyle = decisionColor;
        ctx.font = 'bold 9px monospace';
        ctx.fillText(`[${spotDebug.decision}]`, center.x, center.y + 22);
      }
    });

    // Draw current polygon (calibration)
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

      currentPolygon.forEach((point, index) => {
        ctx.beginPath();
        ctx.arc(point.x, point.y, 8, 0, Math.PI * 2);
        ctx.fillStyle = '#f59e0b';
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.stroke();
        
        ctx.fillStyle = '#000';
        ctx.font = 'bold 12px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText((index + 1).toString(), point.x, point.y);
      });
    }
    
    // Draw frame info (debug)
    if (showDebug && debugInfo?.frameSize) {
      ctx.fillStyle = 'rgba(0,0,0,0.7)';
      ctx.fillRect(5, 5, 180, 20);
      ctx.fillStyle = '#0f0';
      ctx.font = '11px monospace';
      ctx.textAlign = 'left';
      ctx.fillText(`Frame: ${debugInfo.frameSize[0]}x${debugInfo.frameSize[1]}`, 10, 18);
    }
  }, [spots, isCalibrating, currentPolygon, debugInfo, showDebug]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !videoUrl) return;
    setIsVideoReady(false);
    video.src = videoUrl;
    video.load();
  }, [videoUrl]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleLoadedMetadata = () => {
      console.log('Video loaded:', video.videoWidth, video.videoHeight);
      setIsVideoReady(true);
      updateCanvasSize();
      onVideoLoaded?.(video.videoWidth, video.videoHeight);
    };

    const handleCanPlay = () => {
      video.play().catch(err => console.log('Autoplay blocked:', err));
    };

    video.addEventListener('loadedmetadata', handleLoadedMetadata);
    video.addEventListener('canplay', handleCanPlay);
    
    return () => {
      video.removeEventListener('loadedmetadata', handleLoadedMetadata);
      video.removeEventListener('canplay', handleCanPlay);
    };
  }, [updateCanvasSize, onVideoLoaded]);

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

    // Convert client coords to canvas (video) coords
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    const point: Point = {
      x: Math.round((e.clientX - rect.left) * scaleX),
      y: Math.round((e.clientY - rect.top) * scaleY),
    };

    console.log('Click -> video coords:', point, 'canvas:', canvas.width, 'x', canvas.height);
    onCanvasClick(point);
  };

  return (
    <div className="video-wrapper" ref={containerRef}>
      <video ref={videoRef} loop muted playsInline autoPlay />
      <canvas
        ref={canvasRef}
        className={`video-canvas ${isCalibrating ? 'calibration' : ''}`}
        onClick={handleCanvasClick}
      />
      {!isVideoReady && videoUrl && (
        <div className="video-loading">Loading video...</div>
      )}
    </div>
  );
});

VideoPlayer.displayName = 'VideoPlayer';
