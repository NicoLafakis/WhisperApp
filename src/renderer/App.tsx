/**
 * JARVIS Voice Agent - Main React Component
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { AgentState, CostMetrics, Message } from '../shared/types';
import SettingsModal from './SettingsModal';
import './electron.d.ts';

// Audio visualization component
function AudioVisualizer({ isActive, intensity }: { isActive: boolean; intensity: number }) {
  const bars = 5;

  return (
    <div
      className={`audio-visualizer ${isActive ? 'active' : ''}`}
      role="img"
      aria-label={isActive ? 'Audio visualizer showing active audio' : 'Audio visualizer inactive'}
    >
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
    <div
      className={`speaking-orb ${isActive ? 'active' : ''}`}
      role="img"
      aria-label={isActive ? 'JARVIS is speaking' : 'JARVIS voice indicator'}
    >
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
    window.electronAPI.checkFirstRun().then((result) => {
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
    window.electronAPI.startAgent();
  }, []);

  useEffect(() => {
    // Set up event listeners using the secure API
    const cleanupStatus = window.electronAPI.onStatusChanged((state: AgentState) => {
      setAgentState(state);

      // Track speaking state for visualization
      if (state.status === 'speaking') {
        setIsAudioPlaying(true);
      } else if (state.status === 'idle' || state.status === 'error') {
        setIsAudioPlaying(false);
      }
    });

    const cleanupMessage = window.electronAPI.onMessage((message: { role: string; text: string }) => {
      setMessages(prev => [
        ...prev,
        {
          id: Date.now().toString(),
          role: message.role as 'user' | 'assistant',
          content: message.text,
          timestamp: Date.now(),
        },
      ]);
    });

    const cleanupCost = window.electronAPI.onCostUpdated((costMetrics: CostMetrics) => {
      setMetrics(costMetrics);
    });

    const cleanupAudioPlaying = window.electronAPI.onAudioPlaying((data: { intensity: number }) => {
      setIsAudioPlaying(true);
      setAudioIntensity(data.intensity || 0.5);
    });

    const cleanupAudioStopped = window.electronAPI.onAudioStopped(() => {
      setIsAudioPlaying(false);
      setAudioIntensity(0);
    });

    // Get initial state
    window.electronAPI.getAgentState().then((state) => {
      if (state) setAgentState(state);
    });

    return () => {
      cleanupStatus();
      cleanupMessage();
      cleanupCost();
      cleanupAudioPlaying();
      cleanupAudioStopped();
    };
  }, []);

  const triggerReset = () => {
    window.electronAPI.triggerWakeWord();
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

  const getStatusIcon = () => {
    switch (agentState?.status) {
      case 'listening': return '🎤';
      case 'thinking': return '🤔';
      case 'speaking': return '🔊';
      case 'executing': return '⚙️';
      case 'error': return '⚠️';
      default: return '💤';
    }
  };

  const isSpeaking = agentState?.status === 'speaking' || isAudioPlaying;

  return (
    <div className="app" role="application" aria-label="JARVIS Voice Assistant">
      <SettingsModal
        isOpen={showSettings}
        onClose={handleSettingsClose}
        isFirstRun={isFirstRun}
      />

      <button
        type="button"
        className="settings-trigger"
        onClick={() => setShowSettings(true)}
        aria-label="Open settings"
      >
        <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16" aria-hidden="true">
          <path d="M19.14 12.94c.04-.31.06-.63.06-.94 0-.31-.02-.63-.06-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.04.31-.06.63-.06.94s.02.63.06.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/>
        </svg>
      </button>

      <header className="header">
        <h1>JARVIS</h1>
        <div className="status-container">
          <div
            className="status"
            style={{ backgroundColor: getStatusColor() }}
            role="status"
            aria-live="polite"
          >
            <span className="status-icon" aria-hidden="true">{getStatusIcon()}</span>
            {getStatusText()}
          </div>
          {isSpeaking && (
            <AudioVisualizer isActive={true} intensity={audioIntensity || 0.7} />
          )}
        </div>
      </header>

      {/* Speaking visualization orb */}
      <div className="visualization-section">
        <SpeakingOrb isActive={isSpeaking} />
      </div>

      <div className="mode-indicator">
        <span
          className={`mode ${agentState?.mode === 'premium' ? 'premium' : 'efficient'}`}
          role="status"
          aria-label={`Current mode: ${agentState?.mode === 'premium' ? 'Premium' : 'Efficient'}`}
        >
          {agentState?.mode === 'premium' ? '⚡ Premium Mode' : '💰 Efficient Mode'}
        </span>
      </div>

      {metrics && (
        <section className="metrics" aria-label="Cost metrics">
          <div className="metric">
            <span className="label">Today</span>
            <span className="value" aria-label={`Today's cost: $${metrics.todayCost.toFixed(3)}`}>
              ${metrics.todayCost.toFixed(3)}
            </span>
          </div>
          <div className="metric">
            <span className="label">Month</span>
            <span className="value" aria-label={`This month's cost: $${metrics.monthCost.toFixed(2)}`}>
              ${metrics.monthCost.toFixed(2)}
            </span>
          </div>
          <div className="metric">
            <span className="label">Count</span>
            <span className="value" aria-label={`Interaction count: ${metrics.interactionCount}`}>
              {metrics.interactionCount}
            </span>
          </div>
        </section>
      )}

      <section className="messages" aria-label="Conversation history" role="log">
        {messages.length === 0 ? (
          <div className="empty-messages">
            <span>JARVIS is listening...</span>
          </div>
        ) : (
          messages.slice(-10).map((msg) => (
            <article
              key={msg.id}
              className={`message ${msg.role}`}
              aria-label={`${msg.role === 'user' ? 'You' : 'JARVIS'} said`}
            >
              <span className="role">{msg.role === 'user' ? 'You' : 'JARVIS'}:</span>
              <span className="content">{msg.content}</span>
            </article>
          ))
        )}
        <div ref={messagesEndRef} />
      </section>

      <nav className="controls" aria-label="Controls">
        <div className="control-row">
          <button
            type="button"
            className="wake-btn"
            onClick={triggerReset}
            aria-label="Reset conversation and start fresh"
          >
            Reset Conversation
          </button>

          <button
            type="button"
            className="control-btn clear-btn"
            onClick={clearMessages}
            aria-label="Clear all messages"
          >
            <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20" aria-hidden="true">
              <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
            </svg>
          </button>
        </div>
      </nav>
    </div>
  );
}
