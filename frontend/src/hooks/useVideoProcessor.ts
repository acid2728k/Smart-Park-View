import { useRef, useCallback, useEffect, useState } from 'react';
import { ParkingSpot, Point } from '../types';

interface ProcessingResult {
  occupancyMap: Record<string, boolean>;
}

export function useVideoProcessor(
  videoRef: React.RefObject<HTMLVideoElement>,
  canvasRef: React.RefObject<HTMLCanvasElement>,
  spots: ParkingSpot[],
  isMonitoring: boolean
) {
  const [occupancyMap, setOccupancyMap] = useState<Record<string, boolean>>({});
  const wsRef = useRef<WebSocket | null>(null);
  const processingRef = useRef(false);
  const frameIntervalRef = useRef<number | null>(null);

  const connectWebSocket = useCallback(() => {
    const ws = new WebSocket(`ws://${window.location.hostname}:5000/ws`);
    
    ws.onopen = () => {
      console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as ProcessingResult;
        setOccupancyMap(data.occupancyMap);
      } catch (e) {
        console.error('Failed to parse WS message:', e);
      }
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      // Reconnect after 2 seconds
      setTimeout(() => {
        if (isMonitoring) {
          wsRef.current = connectWebSocket();
        }
      }, 2000);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    return ws;
  }, [isMonitoring]);

  const sendFrameToBackend = useCallback(async () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    
    if (!video || !canvas || processingRef.current || video.paused || video.ended) {
      return;
    }

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    processingRef.current = true;

    try {
      // Draw current frame to canvas
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      
      // Get frame as base64
      const frameData = canvas.toDataURL('image/jpeg', 0.8);
      
      // Send via WebSocket if connected
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          type: 'frame',
          data: frameData,
          spots: spots.map(s => ({
            id: s.id,
            polygon: s.polygon,
          })),
        }));
      }
    } catch (e) {
      console.error('Error processing frame:', e);
    } finally {
      processingRef.current = false;
    }
  }, [videoRef, canvasRef, spots]);

  // Connect WebSocket when monitoring starts
  useEffect(() => {
    if (isMonitoring && spots.length > 0) {
      wsRef.current = connectWebSocket();
      
      // Send frames at ~5 FPS
      frameIntervalRef.current = window.setInterval(() => {
        sendFrameToBackend();
      }, 200);
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (frameIntervalRef.current) {
        clearInterval(frameIntervalRef.current);
        frameIntervalRef.current = null;
      }
    };
  }, [isMonitoring, spots, connectWebSocket, sendFrameToBackend]);

  return { occupancyMap };
}
