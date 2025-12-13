/**
 * JARVIS Voice Agent - Main Engine (Autonomous Mode)
 * Orchestrates all components: audio, routing, APIs, and functions
 * Always listening - no wake word required
 */

import { EventEmitter } from 'events';
import { AudioCapture } from './engine/AudioCapture';
import { CostTracker } from './engine/CostTracker';
import { AdaptiveRouter } from './engine/AdaptiveRouter';
import { RealtimeClient } from './services/RealtimeClient';
import { FallbackChain } from './services/FallbackChain';
import { FunctionExecutor } from './functions/executor';
import { JARVIS_FUNCTIONS } from './functions';
import { AgentState, AgentStatus, AgentMode, AudioBuffer, FunctionCall } from '../shared/types';
import { logger } from '../shared/utils/logger';
import { configManager } from '../shared/utils/config';
import Speaker from 'speaker';

// Greetings JARVIS can use on startup
const STARTUP_GREETINGS = [
  "Good to see you. What can I help you with?",
  "Hello. I'm here and ready to assist.",
  "At your service. What would you like me to do?",
  "I'm online and listening. How can I help?",
];

// Follow-up prompts when user doesn't respond
const FOLLOW_UP_PROMPTS = [
  "You there?",
  "Still with me?",
  "Anything I can help with?",
];

export class JarvisEngine extends EventEmitter {
  private audioCapture: AudioCapture;
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

  // Silence tracking for follow-up prompts
  private silenceTimer: NodeJS.Timeout | null = null;
  private silenceTimeoutMs: number = 10000; // 10 seconds
  private hasGreeted: boolean = false;
  private followUpCount: number = 0;
  private maxFollowUps: number = 2; // Max follow-ups before going quiet

  constructor() {
    super();

    const config = configManager.getConfig();

    // Initialize components (no wake word detector needed)
    this.audioCapture = new AudioCapture(config.audio);
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
  }

  async start() {
    if (this.isRunning) {
      logger.warn('JARVIS already running');
      return;
    }

    try {
      logger.info('Starting JARVIS engine (autonomous mode)...');

      // Initialize API clients based on routing decision
      await this.initializeClients();

      // Start audio capture
      this.audioCapture.start();

      this.isRunning = true;

      // Go directly to listening mode - always ready
      this.updateStatus('listening');

      logger.info('JARVIS engine started successfully');
      this.emit('started');

      // Greet the user after a short delay to let everything initialize
      setTimeout(() => {
        this.greetUser();
      }, 1000);

    } catch (error) {
      logger.error('Failed to start JARVIS', { error });
      throw error;
    }
  }

  private async greetUser() {
    if (this.hasGreeted) return;

    const greeting = STARTUP_GREETINGS[Math.floor(Math.random() * STARTUP_GREETINGS.length)];
    logger.info('Greeting user', { greeting });

    this.hasGreeted = true;
    this.updateStatus('speaking');

    // Send greeting through the API to get voice synthesis
    if (this.currentMode === 'premium' && this.realtimeClient) {
      this.realtimeClient.sendText(greeting);
    } else if (this.fallbackChain) {
      // For fallback, synthesize directly
      await this.fallbackChain.synthesizeAndPlay(greeting);
      this.finishInteraction();
    }

    // Emit transcript for UI
    this.emit('transcript', { role: 'assistant', text: greeting });
  }

  private startSilenceTimer() {
    this.clearSilenceTimer();

    // Only start timer if we haven't hit max follow-ups
    if (this.followUpCount >= this.maxFollowUps) {
      logger.info('Max follow-ups reached, staying quiet');
      return;
    }

    this.silenceTimer = setTimeout(() => {
      this.handleSilenceTimeout();
    }, this.silenceTimeoutMs);
  }

  private clearSilenceTimer() {
    if (this.silenceTimer) {
      clearTimeout(this.silenceTimer);
      this.silenceTimer = null;
    }
  }

  private async handleSilenceTimeout() {
    // User hasn't responded, send a follow-up
    const prompt = FOLLOW_UP_PROMPTS[Math.floor(Math.random() * FOLLOW_UP_PROMPTS.length)];
    logger.info('Silence timeout, sending follow-up', { prompt, followUpCount: this.followUpCount });

    this.followUpCount++;
    this.updateStatus('speaking');

    if (this.currentMode === 'premium' && this.realtimeClient) {
      this.realtimeClient.sendText(prompt);
    } else if (this.fallbackChain) {
      await this.fallbackChain.synthesizeAndPlay(prompt);
      this.finishInteraction();
    }

    this.emit('transcript', { role: 'assistant', text: prompt });
  }

  // Reset follow-up count when user actually speaks
  private resetFollowUpCount() {
    this.followUpCount = 0;
  }

  async stop() {
    if (!this.isRunning) {
      return;
    }

    try {
      logger.info('Stopping JARVIS engine...');

      // Clear silence timer
      this.clearSilenceTimer();

      // Stop audio capture
      this.audioCapture.stop();

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
      this.hasGreeted = false;
      this.followUpCount = 0;
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
      // User started speaking - clear silence timer and reset follow-up count
      this.clearSilenceTimer();
      this.resetFollowUpCount();
      this.updateStatus('listening');
    });

    this.realtimeClient.on('speech.stopped', () => {
      this.updateStatus('thinking');
    });

    this.realtimeClient.on('response.done', () => {
      this.audioBuffer = [];

      // Record cost
      this.costTracker.recordRealtimeInteraction(5, 1000); // Estimate
      this.updateMetrics();

      // Finish the interaction (handles audio cleanup and events)
      this.finishInteraction();

      // Start silence timer for follow-up prompts
      this.startSilenceTimer();
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
    // In autonomous mode, always send audio to the API (it handles VAD)
    // Only skip if we're currently speaking (to avoid feedback loop)
    if (this.state.status === 'speaking' || this.state.status === 'error') {
      return;
    }

    this.audioBuffer.push(audioBuffer.data);

    // Send to active client
    if (this.currentMode === 'premium' && this.realtimeClient) {
      this.realtimeClient.sendAudio(audioBuffer.data);
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
        // Finish interaction for fallback mode
        this.finishInteraction();
      }
    } catch (error) {
      logger.error('Failed to process audio', { error });
      this.updateStatus('error');
      this.emit('interaction:complete'); // Still emit complete on error
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

  private isPlayingAudio: boolean = false;

  private playAudio(audioChunk: Buffer) {
    try {
      if (!this.speaker) {
        this.speaker = new Speaker({
          channels: 1,
          bitDepth: 16,
          sampleRate: 24000, // Realtime API outputs 24kHz
        });

        // Track when audio playback finishes
        this.speaker.on('close', () => {
          this.isPlayingAudio = false;
          this.emit('audio:stopped');
          logger.debug('Audio playback finished');
        });
      }

      // Emit audio playing event if not already playing
      if (!this.isPlayingAudio) {
        this.isPlayingAudio = true;
        this.emit('audio:playing');
        logger.debug('Audio playback started');
      }

      this.speaker.write(audioChunk);
    } catch (error) {
      logger.error('Failed to play audio', { error });
    }
  }

  private finishInteraction() {
    // Close speaker to finish audio playback
    if (this.speaker) {
      this.speaker.end();
      this.speaker = null;
    }

    this.isPlayingAudio = false;
    this.emit('audio:stopped');
    this.emit('interaction:complete');
    this.updateStatus('idle');
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

  // Reset conversation state and greet again (can be triggered manually)
  triggerWakeWord() {
    logger.info('Manual trigger - resetting conversation');
    this.followUpCount = 0;
    this.hasGreeted = false;
    this.clearSilenceTimer();
    this.greetUser();
  }
}
