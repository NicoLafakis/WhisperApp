/**
 * JARVIS Voice Agent - Main React Component
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { AgentState, CostMetrics, Message } from '../shared/types';

const { ipcRenderer } = window.require('electron');

// Audio visualization component
function AudioVisualizer({ isActive, intensity }: { isActive: boolean; intensity: number }) {
  const bars = 5;

  return (
    <div className={`audio-visualizer ${isActive ? 'active' : ''}`}>
      {Array.from({ length: bars }).map((_, i) => (
        <div
          key={i}
          className="visualizer-bar"
          style={{
            animationDelay: `${i * 0.1}s`,
            height: isActive ? `${20 + Math.random() * 30 * intensity}px` : '4px',
          }}
        />
      ))}
    </div>
  );
}

// Pulsing orb component for speaking state
function SpeakingOrb({ isActive }: { isActive: boolean }) {
  return (
    <div className={`speaking-orb ${isActive ? 'active' : ''}`}>
      <div className="orb-core" />
      <div className="orb-ring ring-1" />
      <div className="orb-ring ring-2" />
      <div className="orb-ring ring-3" />
    </div>
  );
}

export default function App() {
  const [agentState, setAgentState] = useState<AgentState | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [metrics, setMetrics] = useState<CostMetrics | null>(null);
  const [isMuted, setIsMuted] = useState(false);
  const [autoMuteEnabled, setAutoMuteEnabled] = useState(true);
  const [audioIntensity, setAudioIntensity] = useState(0);
  const [isAudioPlaying, setIsAudioPlaying] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    // Listen for agent status changes
    ipcRenderer.on('agent:status-changed', (_event: any, state: AgentState) => {
      setAgentState(state);

      // Track speaking state for visualization
      if (state.status === 'speaking') {
        setIsAudioPlaying(true);
      } else if (state.status === 'idle' || state.status === 'error') {
        setIsAudioPlaying(false);
      }
    });

    // Listen for messages
    ipcRenderer.on('agent:message', (_event: any, message: any) => {
      setMessages(prev => [
        ...prev,
        {
          id: Date.now().toString(),
          role: message.role,
          content: message.text,
          timestamp: Date.now(),
        },
      ]);
    });

    // Listen for cost updates
    ipcRenderer.on('cost:updated', (_event: any, costMetrics: CostMetrics) => {
      setMetrics(costMetrics);
    });

    // Listen for audio playback events (for visualization)
    ipcRenderer.on('audio:playing', (_event: any, data: { intensity: number }) => {
      setIsAudioPlaying(true);
      setAudioIntensity(data.intensity || 0.5);
    });

    ipcRenderer.on('audio:stopped', () => {
      setIsAudioPlaying(false);
      setAudioIntensity(0);
    });

    // Listen for mute state changes
    ipcRenderer.on('audio:mute-changed', (_event: any, muted: boolean) => {
      setIsMuted(muted);
    });

    // Get initial state
    ipcRenderer.invoke('agent:get-state').then((state: AgentState) => {
      if (state) setAgentState(state);
    });

    // Get initial mute state
    ipcRenderer.invoke('audio:get-mute-state').then((muted: boolean) => {
      setIsMuted(muted);
    });

    return () => {
      ipcRenderer.removeAllListeners('agent:status-changed');
      ipcRenderer.removeAllListeners('agent:message');
      ipcRenderer.removeAllListeners('cost:updated');
      ipcRenderer.removeAllListeners('audio:playing');
      ipcRenderer.removeAllListeners('audio:stopped');
      ipcRenderer.removeAllListeners('audio:mute-changed');
    };
  }, []);

  const triggerWakeWord = () => {
    ipcRenderer.invoke('agent:trigger-wakeword');
  };

  const toggleMute = useCallback(() => {
    ipcRenderer.invoke('audio:toggle-mute');
  }, []);

  const toggleAutoMute = useCallback(() => {
    const newValue = !autoMuteEnabled;
    setAutoMuteEnabled(newValue);
    ipcRenderer.invoke('audio:set-auto-mute', newValue);
  }, [autoMuteEnabled]);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  const getStatusColor = () => {
    switch (agentState?.status) {
      case 'listening': return '#4CAF50';
      case 'thinking': return '#FFC107';
      case 'speaking': return '#2196F3';
      case 'executing': return '#9C27B0';
      case 'error': return '#F44336';
      default: return '#9E9E9E';
    }
  };

  const getStatusText = () => {
    switch (agentState?.status) {
      case 'listening': return 'Listening...';
      case 'thinking': return 'Thinking...';
      case 'speaking': return 'Speaking...';
      case 'executing': return 'Executing...';
      case 'error': return 'Error';
      default: return 'Idle';
    }
  };

  const isSpeaking = agentState?.status === 'speaking' || isAudioPlaying;

  return (
    <div className="app">
      <div className="header">
        <h1>JARVIS</h1>
        <div className="status-container">
          <div className="status" style={{ backgroundColor: getStatusColor() }}>
            {getStatusText()}
          </div>
          {isSpeaking && (
            <AudioVisualizer isActive={true} intensity={audioIntensity || 0.7} />
          )}
        </div>
      </div>

      {/* Speaking visualization orb */}
      <div className="visualization-section">
        <SpeakingOrb isActive={isSpeaking} />
      </div>

      <div className="mode-indicator">
        <span className={`mode ${agentState?.mode === 'premium' ? 'premium' : 'efficient'}`}>
          {agentState?.mode === 'premium' ? 'Premium Mode' : 'Efficient Mode'}
        </span>
      </div>

      {metrics && (
        <div className="metrics">
          <div className="metric">
            <span className="label">Today</span>
            <span className="value">${metrics.todayCost.toFixed(3)}</span>
          </div>
          <div className="metric">
            <span className="label">Month</span>
            <span className="value">${metrics.monthCost.toFixed(2)}</span>
          </div>
          <div className="metric">
            <span className="label">Count</span>
            <span className="value">{metrics.interactionCount}</span>
          </div>
        </div>
      )}

      <div className="messages">
        {messages.length === 0 ? (
          <div className="empty-messages">
            <span>Say "JARVIS" to start a conversation</span>
          </div>
        ) : (
          messages.slice(-10).map((msg) => (
            <div key={msg.id} className={`message ${msg.role}`}>
              <span className="role">{msg.role === 'user' ? 'You' : 'JARVIS'}:</span>
              <span className="content">{msg.content}</span>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="controls">
        <div className="control-row">
          <button
            className={`control-btn mute-btn ${isMuted ? 'muted' : ''}`}
            onClick={toggleMute}
            title={isMuted ? 'Unmute system audio' : 'Mute system audio'}
          >
            {isMuted ? (
              <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
                <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/>
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
                <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
              </svg>
            )}
          </button>

          <button
            className={`control-btn auto-mute-btn ${autoMuteEnabled ? 'enabled' : ''}`}
            onClick={toggleAutoMute}
            title={autoMuteEnabled ? 'Disable auto-mute on wake' : 'Enable auto-mute on wake'}
          >
            <span className="auto-mute-icon">A</span>
            {autoMuteEnabled ? (
              <svg viewBox="0 0 24 24" fill="currentColor" width="14" height="14" className="auto-mute-status">
                <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
              </svg>
            ) : null}
          </button>

          <button className="wake-btn" onClick={triggerWakeWord}>
            Trigger Wake Word
          </button>

          <button
            className="control-btn clear-btn"
            onClick={clearMessages}
            title="Clear messages"
          >
            <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
              <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
