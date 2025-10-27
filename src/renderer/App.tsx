/**
 * JARVIS Voice Agent - Main React Component
 */

import React, { useState, useEffect } from 'react';
import { AgentState, CostMetrics, Message } from '../shared/types';

const { ipcRenderer } = window.require('electron');

export default function App() {
  const [agentState, setAgentState] = useState<AgentState | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [metrics, setMetrics] = useState<CostMetrics | null>(null);

  useEffect(() => {
    // Listen for agent status changes
    ipcRenderer.on('agent:status-changed', (_event: any, state: AgentState) => {
      setAgentState(state);
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

    // Get initial state
    ipcRenderer.invoke('agent:get-state').then((state: AgentState) => {
      if (state) setAgentState(state);
    });

    return () => {
      ipcRenderer.removeAllListeners('agent:status-changed');
      ipcRenderer.removeAllListeners('agent:message');
      ipcRenderer.removeAllListeners('cost:updated');
    };
  }, []);

  const triggerWakeWord = () => {
    ipcRenderer.invoke('agent:trigger-wakeword');
  };

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

  return (
    <div className="app">
      <div className="header">
        <h1>JARVIS</h1>
        <div className="status" style={{ backgroundColor: getStatusColor() }}>
          {getStatusText()}
        </div>
      </div>

      <div className="mode-indicator">
        <span className={`mode ${agentState?.mode === 'premium' ? 'premium' : 'efficient'}`}>
          {agentState?.mode === 'premium' ? 'Premium Mode' : 'Efficient Mode'}
        </span>
      </div>

      {metrics && (
        <div className="metrics">
          <div className="metric">
            <span className="label">Today:</span>
            <span className="value">${metrics.todayCost.toFixed(3)}</span>
          </div>
          <div className="metric">
            <span className="label">Month:</span>
            <span className="value">${metrics.monthCost.toFixed(2)}</span>
          </div>
          <div className="metric">
            <span className="label">Interactions:</span>
            <span className="value">{metrics.interactionCount}</span>
          </div>
        </div>
      )}

      <div className="messages">
        {messages.slice(-5).map((msg) => (
          <div key={msg.id} className={`message ${msg.role}`}>
            <span className="role">{msg.role === 'user' ? 'You' : 'JARVIS'}:</span>
            <span className="content">{msg.content}</span>
          </div>
        ))}
      </div>

      <div className="controls">
        <button className="wake-btn" onClick={triggerWakeWord}>
          Trigger Wake Word
        </button>
      </div>
    </div>
  );
}
