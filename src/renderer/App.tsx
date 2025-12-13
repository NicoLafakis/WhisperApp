/**
 * JARVIS Voice Agent - Main React Component
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { AgentState, CostMetrics, Message } from '../shared/types';
import SettingsModal from './SettingsModal';

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
  const [audioIntensity, setAudioIntensity] = useState(0);
  const [isAudioPlaying, setIsAudioPlaying] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [isFirstRun, setIsFirstRun] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Check for first run on mount
  useEffect(() => {
    ipcRenderer.invoke('settings:check-first-run').then((result: { isFirstRun: boolean; showSettings: boolean }) => {
      setIsFirstRun(result.isFirstRun);
      if (result.showSettings) {
        setShowSettings(true);
      }
    });
  }, []);

  const handleSettingsClose = useCallback(() => {
    setShowSettings(false);
    setIsFirstRun(false);
    // Notify main process that setup is complete
    ipcRenderer.invoke('agent:start');
  }, []);

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

    // Get initial state
    ipcRenderer.invoke('agent:get-state').then((state: AgentState) => {
      if (state) setAgentState(state);
    });

    return () => {
      ipcRenderer.removeAllListeners('agent:status-changed');
      ipcRenderer.removeAllListeners('agent:message');
      ipcRenderer.removeAllListeners('cost:updated');
      ipcRenderer.removeAllListeners('audio:playing');
      ipcRenderer.removeAllListeners('audio:stopped');
    };
  }, []);

  const triggerReset = () => {
    ipcRenderer.invoke('agent:trigger-wakeword');
  };

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
      <SettingsModal
        isOpen={showSettings}
        onClose={handleSettingsClose}
        isFirstRun={isFirstRun}
      />

      <button
        type="button"
        className="settings-trigger"
        onClick={() => setShowSettings(true)}
        title="Settings"
      >
        <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16">
          <path d="M19.14 12.94c.04-.31.06-.63.06-.94 0-.31-.02-.63-.06-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.04.31-.06.63-.06.94s.02.63.06.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/>
        </svg>
      </button>

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
            <span>JARVIS is listening...</span>
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
          <button type="button" className="wake-btn" onClick={triggerReset}>
            Reset Conversation
          </button>

          <button
            type="button"
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
