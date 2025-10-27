/**
 * JARVIS Voice Agent - Main Engine
 * Orchestrates all components: wake word, audio, routing, APIs, and functions
 */

import { EventEmitter } from 'events';
import { AudioCapture } from './engine/AudioCapture';
import { WakeWordDetector } from './engine/WakeWordDetector';
import { CostTracker } from './engine/CostTracker';
import { AdaptiveRouter } from './engine/AdaptiveRouter';
import { RealtimeClient } from './services/RealtimeClient';
import { FallbackChain } from './services/FallbackChain';
import { FunctionExecutor } from './functions/executor';
import { JARVIS_FUNCTIONS } from './functions';
import { AgentState, AgentStatus, AgentMode, AudioBuffer, FunctionCall } from '../shared/types';
import { logger } from '../shared/utils/logger';
import { configManager } from '../shared/utils/config';
import { Writable } from 'stream';
import Speaker from 'speaker';

export class JarvisEngine extends EventEmitter {
  private audioCapture: AudioCapture;
  private wakeWordDetector: WakeWordDetector;
  private costTracker: CostTracker;
  private adaptiveRouter: AdaptiveRouter;
  private realtimeClient: RealtimeClient | null = null;
  private fallbackChain: FallbackChain | null = null;
  private functionExecutor: FunctionExecutor;
  private speaker: Speaker | null = null;

  private state: AgentState;
  private isRunning: boolean = false;
  private currentMode: AgentMode = 'premium';
  private audioBuffer: Buffer[] = [];

  constructor() {
    super();

    const config = configManager.getConfig();

    // Initialize components
    this.audioCapture = new AudioCapture(config.audio);
    this.wakeWordDetector = new WakeWordDetector(config.wakeWord.keyword, config.wakeWord.sensitivity);
    this.costTracker = new CostTracker(config.routing.dailyBudget, config.routing.monthlyBudget);
    this.adaptiveRouter = new AdaptiveRouter(this.costTracker, config.routing);
    this.functionExecutor = new FunctionExecutor(config.security.blocked, config.security.requireConfirmation);

    // Initialize state
    this.state = {
      status: 'idle',
      mode: config.routing.defaultMode,
      isWakeWordActive: false,
      currentInteraction: null,
      metrics: this.costTracker.getMetrics(),
    };

    this.setupEventHandlers();
  }

  private setupEventHandlers() {
    // Audio capture events
    this.audioCapture.on('audio', (audioBuffer: AudioBuffer) => {
      this.handleAudioInput(audioBuffer);
    });

    this.audioCapture.on('error', (error: Error) => {
      logger.error('Audio capture error', { error: error.message });
      this.updateStatus('error');
    });

    // Wake word events
    this.wakeWordDetector.on('wakeword', () => {
      this.handleWakeWord();
    });
  }

  async start() {
    if (this.isRunning) {
      logger.warn('JARVIS already running');
      return;
    }

    try {
      logger.info('Starting JARVIS engine...');

      // Start audio capture
      this.audioCapture.start();

      // Start wake word detector
      await this.wakeWordDetector.start();

      // Initialize API clients based on routing decision
      await this.initializeClients();

      this.isRunning = true;
      this.updateStatus('idle');

      logger.info('JARVIS engine started successfully');
      this.emit('started');

    } catch (error) {
      logger.error('Failed to start JARVIS', { error });
      throw error;
    }
  }

  async stop() {
    if (!this.isRunning) {
      return;
    }

    try {
      logger.info('Stopping JARVIS engine...');

      // Stop audio capture
      this.audioCapture.stop();

      // Stop wake word detector
      this.wakeWordDetector.stop();

      // Disconnect clients
      if (this.realtimeClient) {
        this.realtimeClient.disconnect();
      }

      // Close speaker
      if (this.speaker) {
        this.speaker.end();
        this.speaker = null;
      }

      this.isRunning = false;
      this.updateStatus('idle');

      logger.info('JARVIS engine stopped');
      this.emit('stopped');

    } catch (error) {
      logger.error('Failed to stop JARVIS', { error });
    }
  }

  private async initializeClients() {
    const config = configManager.getConfig();
    const routingDecision = this.adaptiveRouter.route();

    this.currentMode = routingDecision.mode;
    this.state.mode = routingDecision.mode;

    logger.info('Initializing clients', { mode: this.currentMode });

    if (this.currentMode === 'premium') {
      // Initialize Realtime API
      this.realtimeClient = new RealtimeClient({
        apiKey: config.openai.apiKey,
        model: 'gpt-4o-realtime-preview-2024-10-01',
        voice: config.voice.name,
        tools: JARVIS_FUNCTIONS,
      });

      this.setupRealtimeHandlers();
      await this.realtimeClient.connect();

    } else {
      // Initialize fallback chain
      this.fallbackChain = new FallbackChain({
        openaiApiKey: config.openai.apiKey,
        elevenlabsApiKey: config.elevenlabs.apiKey,
        elevenlabsVoiceId: config.elevenlabs.voiceId,
        tools: JARVIS_FUNCTIONS,
      });

      this.setupFallbackHandlers();
    }
  }

  private setupRealtimeHandlers() {
    if (!this.realtimeClient) return;

    this.realtimeClient.on('audio.delta', (chunk: Buffer) => {
      this.playAudio(chunk);
    });

    this.realtimeClient.on('text.delta', (text: string) => {
      this.emit('transcript', { role: 'assistant', text });
    });

    this.realtimeClient.on('function.call', async (functionCall: FunctionCall) => {
      await this.handleFunctionCall(functionCall);
    });

    this.realtimeClient.on('speech.started', () => {
      this.updateStatus('listening');
    });

    this.realtimeClient.on('speech.stopped', () => {
      this.updateStatus('thinking');
    });

    this.realtimeClient.on('response.done', () => {
      this.updateStatus('idle');
      this.audioBuffer = [];

      // Record cost
      this.costTracker.recordRealtimeInteraction(5, 1000); // Estimate
      this.updateMetrics();
    });
  }

  private setupFallbackHandlers() {
    if (!this.fallbackChain) return;

    this.fallbackChain.on('stage', (stage: string) => {
      logger.info('Fallback stage', { stage });
      if (stage === 'transcribing') this.updateStatus('listening');
      if (stage === 'reasoning') this.updateStatus('thinking');
      if (stage === 'synthesizing') this.updateStatus('speaking');
    });

    this.fallbackChain.on('transcription', (text: string) => {
      this.emit('transcript', { role: 'user', text });
    });

    this.fallbackChain.on('response', (text: string) => {
      this.emit('transcript', { role: 'assistant', text });
    });

    this.fallbackChain.on('audio', (audioBuffer: Buffer) => {
      this.playAudio(audioBuffer);
    });

    this.fallbackChain.on('function.calls', async (calls: any[]) => {
      for (const call of calls) {
        await this.handleFunctionCall({
          name: call.function.name,
          arguments: JSON.parse(call.function.arguments),
          callId: call.id,
        });
      }
    });
  }

  private handleAudioInput(audioBuffer: AudioBuffer) {
    // Feed to wake word detector
    if (this.state.status === 'idle') {
      this.wakeWordDetector.processAudio(audioBuffer.data);
    }

    // If actively listening, buffer the audio
    if (this.state.status === 'listening') {
      this.audioBuffer.push(audioBuffer.data);

      // Send to active client
      if (this.currentMode === 'premium' && this.realtimeClient) {
        this.realtimeClient.sendAudio(audioBuffer.data);
      }
    }
  }

  private async handleWakeWord() {
    logger.info('Wake word detected!');
    this.updateStatus('listening');
    this.audioBuffer = [];

    // Re-evaluate routing decision
    const routingDecision = this.adaptiveRouter.route();

    // Switch modes if needed
    if (routingDecision.mode !== this.currentMode) {
      logger.info('Switching mode', { from: this.currentMode, to: routingDecision.mode });
      this.currentMode = routingDecision.mode;
      await this.initializeClients();
    }

    // Start listening
    if (this.currentMode === 'premium' && this.realtimeClient) {
      // Realtime API handles VAD automatically
      logger.info('Listening via Realtime API...');
    } else if (this.currentMode === 'efficient') {
      // For fallback, we need to manually detect end of speech
      logger.info('Listening via fallback chain...');

      // Simple timeout-based approach (in production, use proper VAD)
      setTimeout(() => {
        this.processBufferedAudio();
      }, 3000); // 3 seconds of silence
    }
  }

  private async processBufferedAudio() {
    if (this.audioBuffer.length === 0) {
      this.updateStatus('idle');
      return;
    }

    const fullAudioBuffer = Buffer.concat(this.audioBuffer);

    try {
      if (this.currentMode === 'premium' && this.realtimeClient) {
        this.realtimeClient.commitAudio();
      } else if (this.currentMode === 'efficient' && this.fallbackChain) {
        this.updateStatus('thinking');
        await this.fallbackChain.processAudio(fullAudioBuffer);
        this.updateStatus('idle');
      }
    } catch (error) {
      logger.error('Failed to process audio', { error });
      this.updateStatus('error');
    }

    this.audioBuffer = [];
  }

  private async handleFunctionCall(functionCall: FunctionCall) {
    logger.info('Handling function call', { functionCall });

    try {
      const result = await this.functionExecutor.execute(functionCall.name, functionCall.arguments);

      // Send result back to the API
      if (this.currentMode === 'premium' && this.realtimeClient) {
        this.realtimeClient.sendFunctionResult(functionCall.callId, result);
      }

      this.emit('function.executed', { call: functionCall, result });

    } catch (error: any) {
      logger.error('Function execution failed', { error: error.message });

      if (this.currentMode === 'premium' && this.realtimeClient) {
        this.realtimeClient.sendFunctionResult(functionCall.callId, {
          error: error.message,
        });
      }
    }
  }

  private playAudio(audioChunk: Buffer) {
    try {
      if (!this.speaker) {
        this.speaker = new Speaker({
          channels: 1,
          bitDepth: 16,
          sampleRate: 24000, // Realtime API outputs 24kHz
        });
      }

      this.speaker.write(audioChunk);
    } catch (error) {
      logger.error('Failed to play audio', { error });
    }
  }

  private updateStatus(status: AgentStatus) {
    this.state.status = status;
    this.emit('status', this.state);
  }

  private updateMetrics() {
    this.state.metrics = this.costTracker.getMetrics();
    this.emit('metrics', this.state.metrics);
  }

  getState(): AgentState {
    return { ...this.state };
  }

  forceMode(mode: AgentMode | null) {
    this.adaptiveRouter.setForcedMode(mode);
    logger.info('Forced mode set', { mode });
  }

  // Trigger wake word manually (for testing)
  triggerWakeWord() {
    this.wakeWordDetector.simulateWakeWord();
  }
}
