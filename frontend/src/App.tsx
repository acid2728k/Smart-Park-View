import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Eye, Maximize2 } from 'lucide-react';
import { SetupScreen } from './components/SetupScreen';
import { SidePanel } from './components/SidePanel';
import { VideoPlayer, VideoPlayerRef } from './components/VideoPlayer';
import { CalibrationOverlay } from './components/CalibrationOverlay';
import { useFullscreen } from './hooks/useFullscreen';
import { saveConfig, loadConfig, clearConfig } from './utils/storage';
import { AppMode, ParkingSpot, ParkingStats, Point, VideoSource } from './types';

function App() {
  const [mode, setMode] = useState<AppMode>('setup');
  const [spots, setSpots] = useState<ParkingSpot[]>([]);
  const [videoUrl, setVideoUrl] = useState<string>('');
  const [totalSpotCount, setTotalSpotCount] = useState(0);
  const [currentSpotIndex, setCurrentSpotIndex] = useState(0);
  const [currentPolygon, setCurrentPolygon] = useState<Point[]>([]);
  const [isPanelHidden, setIsPanelHidden] = useState(false);
  const [occupancyMap, setOccupancyMap] = useState<Record<string, boolean>>({});
  
  const videoPlayerRef = useRef<VideoPlayerRef>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const frameIntervalRef = useRef<number | null>(null);
  
  const { isFullscreen, toggleFullscreen } = useFullscreen();

  // Load saved config on mount
  useEffect(() => {
    const savedConfig = loadConfig();
    if (savedConfig && savedConfig.spots.length > 0) {
      setSpots(savedConfig.spots);
      setVideoUrl(savedConfig.videoSource);
      setMode('monitoring');
    }
  }, []);

  // WebSocket connection for monitoring
  useEffect(() => {
    if (mode !== 'monitoring' || spots.length === 0) return;

    const connectWebSocket = () => {
      const ws = new WebSocket(`ws://${window.location.hostname}:5001/ws`);
      
      ws.onopen = () => {
        console.log('WebSocket connected');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.occupancyMap) {
            setOccupancyMap(data.occupancyMap);
          }
        } catch (e) {
          console.error('Failed to parse WS message:', e);
        }
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected, reconnecting...');
        setTimeout(() => {
          if (mode === 'monitoring') {
            wsRef.current = connectWebSocket();
          }
        }, 2000);
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

      return ws;
    };

    wsRef.current = connectWebSocket();

    // Send frames periodically
    const sendFrame = () => {
      const video = videoPlayerRef.current?.getVideoElement();
      const canvas = videoPlayerRef.current?.getCanvasElement();
      
      if (!video || !canvas || video.paused || video.ended) return;
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

      const tempCanvas = document.createElement('canvas');
      tempCanvas.width = video.videoWidth;
      tempCanvas.height = video.videoHeight;
      const ctx = tempCanvas.getContext('2d');
      if (!ctx) return;

      ctx.drawImage(video, 0, 0);
      const frameData = tempCanvas.toDataURL('image/jpeg', 0.7);

      wsRef.current.send(JSON.stringify({
        type: 'frame',
        data: frameData,
        spots: spots.map(s => ({
          id: s.id,
          polygon: s.polygon,
        })),
      }));
    };

    frameIntervalRef.current = window.setInterval(sendFrame, 500); // 2 FPS

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
  }, [mode, spots]);

  // Update spots with occupancy data
  const spotsWithOccupancy = spots.map(spot => ({
    ...spot,
    isOccupied: occupancyMap[spot.id] ?? spot.isOccupied,
  }));

  const stats: ParkingStats = {
    total: spotsWithOccupancy.length,
    free: spotsWithOccupancy.filter(s => !s.isOccupied).length,
    occupied: spotsWithOccupancy.filter(s => s.isOccupied).length,
  };

  const handleSetupComplete = useCallback((videoSource: VideoSource, spotCount: number) => {
    let url: string = '';
    
    if (videoSource.type === 'file' && videoSource.file) {
      // Create object URL from file
      url = URL.createObjectURL(videoSource.file);
      console.log('Created video URL from file:', url);
    } else if (videoSource.url) {
      url = videoSource.url;
      console.log('Using video URL:', url);
    } else if (videoSource.type === 'camera') {
      // Handle camera in a separate effect
      setMode('calibration');
      setTotalSpotCount(spotCount);
      setCurrentSpotIndex(0);
      setSpots([]);
      setCurrentPolygon([]);
      
      navigator.mediaDevices.getUserMedia({ video: true })
        .then(stream => {
          const video = videoPlayerRef.current?.getVideoElement();
          if (video) {
            video.srcObject = stream;
            video.play();
          }
        })
        .catch(err => console.error('Camera access denied:', err));
      return;
    }

    if (url) {
      setVideoUrl(url);
    }
    setTotalSpotCount(spotCount);
    setCurrentSpotIndex(0);
    setSpots([]);
    setCurrentPolygon([]);
    setMode('calibration');
  }, []);

  const handleCanvasClick = useCallback((point: Point) => {
    if (mode !== 'calibration') return;
    setCurrentPolygon(prev => [...prev, point]);
  }, [mode]);

  const handleConfirmSpot = useCallback(() => {
    if (currentPolygon.length < 3) return;

    const newSpot: ParkingSpot = {
      id: `spot-${currentSpotIndex + 1}`,
      name: `Место ${currentSpotIndex + 1}`,
      polygon: [...currentPolygon],
      isOccupied: false,
    };

    setSpots(prev => [...prev, newSpot]);
    setCurrentPolygon([]);
    setCurrentSpotIndex(prev => prev + 1);
  }, [currentPolygon, currentSpotIndex]);

  const handleUndoPoint = useCallback(() => {
    setCurrentPolygon(prev => prev.slice(0, -1));
  }, []);

  const handleSkipSpot = useCallback(() => {
    setCurrentPolygon([]);
    setCurrentSpotIndex(prev => prev + 1);
  }, []);

  const handleFinishCalibration = useCallback(() => {
    // Save config
    saveConfig({
      spots,
      videoSource: videoUrl,
      sourceType: 'file',
    });
    setMode('monitoring');
  }, [spots, videoUrl]);

  const handleReset = useCallback(() => {
    clearConfig();
    setMode('setup');
    setSpots([]);
    setVideoUrl('');
    setCurrentPolygon([]);
    setCurrentSpotIndex(0);
    setOccupancyMap({});
  }, []);

  if (mode === 'setup') {
    return <SetupScreen onComplete={handleSetupComplete} />;
  }

  return (
    <div className={`app ${isFullscreen ? 'fullscreen' : ''}`}>
      {mode === 'monitoring' && (
        <SidePanel
          spots={spotsWithOccupancy}
          stats={stats}
          isHidden={isPanelHidden}
          onToggleHide={() => setIsPanelHidden(!isPanelHidden)}
          onToggleFullscreen={toggleFullscreen}
          onReset={handleReset}
        />
      )}

      <div className="video-container">
        {isPanelHidden && mode === 'monitoring' && (
          <button
            className="btn-icon toggle-panel-btn"
            onClick={() => setIsPanelHidden(false)}
          >
            <Eye size={18} />
          </button>
        )}

        <div className="floating-controls">
          {mode === 'calibration' && (
            <button className="btn-icon" onClick={toggleFullscreen}>
              <Maximize2 size={18} />
            </button>
          )}
        </div>

        <VideoPlayer
          ref={videoPlayerRef}
          videoUrl={videoUrl}
          spots={mode === 'monitoring' ? spotsWithOccupancy : spots}
          isCalibrating={mode === 'calibration'}
          currentPolygon={currentPolygon}
          onCanvasClick={handleCanvasClick}
        />

        {mode === 'calibration' && (
          <CalibrationOverlay
            currentSpotIndex={currentSpotIndex}
            totalSpots={totalSpotCount}
            pointsDrawn={currentPolygon.length}
            onConfirmSpot={handleConfirmSpot}
            onUndoPoint={handleUndoPoint}
            onSkipSpot={handleSkipSpot}
            onFinishCalibration={handleFinishCalibration}
          />
        )}
      </div>
    </div>
  );
}

export default App;
