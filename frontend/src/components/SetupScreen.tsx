import React, { useState, useRef } from 'react';
import { Car, Upload } from 'lucide-react';
import { VideoSource } from '../types';

interface SetupScreenProps {
  onComplete: (videoSource: VideoSource, spotCount: number) => void;
}

export function SetupScreen({ onComplete }: SetupScreenProps) {
  const [sourceType, setSourceType] = useState<'file' | 'camera' | 'stream'>('file');
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [streamUrl, setStreamUrl] = useState('');
  const [spotCount, setSpotCount] = useState(6);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    let videoSource: VideoSource;
    
    if (sourceType === 'file') {
      if (videoFile) {
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

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setVideoFile(file);
    }
  };

  const handleFileButtonClick = () => {
    fileInputRef.current?.click();
  };

  const isValid = () => {
    if (spotCount < 1) return false;
    if (sourceType === 'file' && !videoFile) return false;
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
        <h2>Parking Setup</h2>

        <div className="setup-field">
          <label>Video Source</label>
          <select
            value={sourceType}
            onChange={(e) => {
              setSourceType(e.target.value as 'file' | 'camera' | 'stream');
              setVideoFile(null);
            }}
          >
            <option value="file">Video File</option>
            <option value="camera">Webcam</option>
            <option value="stream">IP Stream (RTSP/HTTP)</option>
          </select>
        </div>

        {sourceType === 'file' && (
          <div className="setup-field">
            <label>Select Video File</label>
            <input
              ref={fileInputRef}
              type="file"
              accept="video/*"
              onChange={handleFileSelect}
              style={{ display: 'none' }}
            />
            <button
              type="button"
              className="file-select-btn"
              onClick={handleFileButtonClick}
            >
              <Upload size={18} />
              {videoFile ? videoFile.name : 'Choose file...'}
            </button>
            {videoFile && (
              <p className="file-info">
                Size: {(videoFile.size / (1024 * 1024)).toFixed(2)} MB
              </p>
            )}
          </div>
        )}

        {sourceType === 'stream' && (
          <div className="setup-field">
            <label>Stream URL</label>
            <input
              type="text"
              placeholder="rtsp://... or http://..."
              value={streamUrl}
              onChange={(e) => setStreamUrl(e.target.value)}
            />
          </div>
        )}

        {sourceType === 'camera' && (
          <div className="setup-field">
            <p className="camera-info">
              After clicking "Start Calibration", the browser will request camera access.
            </p>
          </div>
        )}

        <div className="setup-field">
          <label>Number of Parking Spots</label>
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
          Start Calibration
        </button>
      </form>
    </div>
  );
}
