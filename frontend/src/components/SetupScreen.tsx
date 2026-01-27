import React, { useState } from 'react';
import { Car } from 'lucide-react';
import { VideoSource } from '../types';

interface SetupScreenProps {
  onComplete: (videoSource: VideoSource, spotCount: number) => void;
}

export function SetupScreen({ onComplete }: SetupScreenProps) {
  const [sourceType, setSourceType] = useState<'file' | 'camera' | 'stream'>('file');
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [streamUrl, setStreamUrl] = useState('');
  const [spotCount, setSpotCount] = useState(6);
  const [useDefaultVideo, setUseDefaultVideo] = useState(true);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    let videoSource: VideoSource;
    
    if (sourceType === 'file') {
      if (useDefaultVideo) {
        videoSource = { type: 'file', url: '/1087118309-test.mp4' };
      } else if (videoFile) {
        videoSource = { type: 'file', file: videoFile };
      } else {
        return;
      }
    } else if (sourceType === 'stream') {
      if (!streamUrl) return;
      videoSource = { type: 'stream', url: streamUrl };
    } else {
      videoSource = { type: 'camera' };
    }
    
    onComplete(videoSource, spotCount);
  };

  const isValid = () => {
    if (spotCount < 1) return false;
    if (sourceType === 'file' && !useDefaultVideo && !videoFile) return false;
    if (sourceType === 'stream' && !streamUrl) return false;
    return true;
  };

  return (
    <div className="setup-screen">
      <div className="setup-logo">
        <Car size={48} />
        <h1>Smart Park View</h1>
      </div>

      <form className="setup-card" onSubmit={handleSubmit}>
        <h2>Настройка парковки</h2>

        <div className="setup-field">
          <label>Источник видео</label>
          <select
            value={sourceType}
            onChange={(e) => setSourceType(e.target.value as 'file' | 'camera' | 'stream')}
          >
            <option value="file">Видеофайл</option>
            <option value="camera">Веб-камера</option>
            <option value="stream">IP-поток (RTSP/HTTP)</option>
          </select>
        </div>

        {sourceType === 'file' && (
          <>
            <div className="setup-field">
              <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={useDefaultVideo}
                  onChange={(e) => setUseDefaultVideo(e.target.checked)}
                  style={{ width: 'auto' }}
                />
                <span>Использовать тестовое видео (1087118309-test.mp4)</span>
              </label>
            </div>
            
            {!useDefaultVideo && (
              <div className="setup-field">
                <label>Выберите видеофайл</label>
                <input
                  type="file"
                  accept="video/*"
                  onChange={(e) => setVideoFile(e.target.files?.[0] || null)}
                />
              </div>
            )}
          </>
        )}

        {sourceType === 'stream' && (
          <div className="setup-field">
            <label>URL потока</label>
            <input
              type="text"
              placeholder="rtsp://... или http://..."
              value={streamUrl}
              onChange={(e) => setStreamUrl(e.target.value)}
            />
          </div>
        )}

        <div className="setup-field">
          <label>Количество парковочных мест</label>
          <input
            type="number"
            min="1"
            max="100"
            value={spotCount}
            onChange={(e) => setSpotCount(parseInt(e.target.value) || 1)}
          />
        </div>

        <button
          type="submit"
          className="btn btn-primary btn-full"
          disabled={!isValid()}
        >
          Начать калибровку
        </button>
      </form>
    </div>
  );
}
