/**
 * JARVIS Voice Agent - OpenAI Realtime API Client
 * WebSocket-based speech-to-speech communication with automatic reconnection
 */

import { EventEmitter } from 'events';
import WebSocket from 'ws';
import { RealtimeConfig, FunctionDefinition, FunctionCall } from '../../shared/types';
import { logger } from '../../shared/utils/logger';

interface RealtimeEvent {
  type: string;
  [key: string]: any;
}

interface ReconnectionConfig {
  enabled: boolean;
  maxAttempts: number;
  initialDelayMs: number;
  maxDelayMs: number;
  backoffMultiplier: number;
}

const DEFAULT_RECONNECTION_CONFIG: ReconnectionConfig = {
  enabled: true,
  maxAttempts: 5,
  initialDelayMs: 1000,
  maxDelayMs: 30000,
  backoffMultiplier: 2,
};

export class RealtimeClient extends EventEmitter {
  private ws: WebSocket | null = null;
  private config: RealtimeConfig;
  private reconnectionConfig: ReconnectionConfig;
  private isConnected: boolean = false;
  private sessionId: string | null = null;

  // Reconnection state
  private reconnectAttempts: number = 0;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private isReconnecting: boolean = false;
  private intentionalDisconnect: boolean = false;
  private connectionPromise: Promise<void> | null = null;

  constructor(config: RealtimeConfig, reconnectionConfig?: Partial<ReconnectionConfig>) {
    super();
    this.config = config;
    this.reconnectionConfig = { ...DEFAULT_RECONNECTION_CONFIG, ...reconnectionConfig };
  }

  /**
   * Connect to the Realtime API with automatic reconnection support
   */
  async connect(): Promise<void> {
    if (this.isConnected) {
      logger.warn('Realtime client already connected');
      return;
    }

    // If already connecting, return the existing promise
    if (this.connectionPromise) {
      return this.connectionPromise;
    }

    this.intentionalDisconnect = false;
    this.connectionPromise = this.establishConnection();

    try {
      await this.connectionPromise;
    } finally {
      this.connectionPromise = null;
    }
  }

  private async establishConnection(): Promise<void> {
    const url = 'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01';

    return new Promise((resolve, reject) => {
      try {
        logger.info('Connecting to Realtime API...', {
          attempt: this.reconnectAttempts + 1,
          maxAttempts: this.reconnectionConfig.maxAttempts,
        });

        this.ws = new WebSocket(url, {
          headers: {
            'Authorization': `Bearer ${this.config.apiKey}`,
            'OpenAI-Beta': 'realtime=v1',
          },
        });

        const connectionTimeout = setTimeout(() => {
          if (!this.isConnected) {
            this.ws?.close();
            reject(new Error('Connection timeout'));
          }
        }, 30000); // 30 second connection timeout

        this.ws.on('open', () => {
          clearTimeout(connectionTimeout);
          logger.info('Realtime API connected');
          this.isConnected = true;
          this.isReconnecting = false;
          this.reconnectAttempts = 0;
          this.initializeSession();
          resolve();
        });

        this.ws.on('message', (data: WebSocket.Data) => {
          this.handleMessage(data);
        });

        this.ws.on('error', (error) => {
          clearTimeout(connectionTimeout);
          logger.error('Realtime API error', { error: error.message });
          this.emit('error', error);

          // Only reject if we haven't connected yet
          if (!this.isConnected) {
            reject(error);
          }
        });

        this.ws.on('close', (code, reason) => {
          clearTimeout(connectionTimeout);
          const wasConnected = this.isConnected;
          this.isConnected = false;

          logger.info('Realtime API disconnected', {
            code,
            reason: reason?.toString(),
            intentional: this.intentionalDisconnect,
          });

          this.emit('disconnected', { code, reason: reason?.toString() });

          // Only attempt reconnection if:
          // 1. Reconnection is enabled
          // 2. This was not an intentional disconnect
          // 3. We were previously connected (not a failed initial connection)
          if (this.reconnectionConfig.enabled && !this.intentionalDisconnect && wasConnected) {
            this.scheduleReconnection();
          }
        });

      } catch (error) {
        logger.error('Failed to connect to Realtime API', { error });
        reject(error);
      }
    });
  }

  /**
   * Schedule a reconnection attempt with exponential backoff
   */
  private scheduleReconnection(): void {
    if (this.isReconnecting || this.intentionalDisconnect) {
      return;
    }

    if (this.reconnectAttempts >= this.reconnectionConfig.maxAttempts) {
      logger.error('Max reconnection attempts reached', {
        attempts: this.reconnectAttempts,
        maxAttempts: this.reconnectionConfig.maxAttempts,
      });
      this.emit('reconnection.failed', {
        attempts: this.reconnectAttempts,
        maxAttempts: this.reconnectionConfig.maxAttempts,
      });
      return;
    }

    this.isReconnecting = true;
    this.reconnectAttempts++;

    // Calculate delay with exponential backoff
    const delay = Math.min(
      this.reconnectionConfig.initialDelayMs * Math.pow(this.reconnectionConfig.backoffMultiplier, this.reconnectAttempts - 1),
      this.reconnectionConfig.maxDelayMs
    );

    logger.info('Scheduling reconnection', {
      attempt: this.reconnectAttempts,
      maxAttempts: this.reconnectionConfig.maxAttempts,
      delayMs: delay,
    });

    this.emit('reconnecting', {
      attempt: this.reconnectAttempts,
      maxAttempts: this.reconnectionConfig.maxAttempts,
      delayMs: delay,
    });

    this.reconnectTimeout = setTimeout(async () => {
      this.reconnectTimeout = null;

      try {
        await this.establishConnection();
        logger.info('Reconnection successful', { attempt: this.reconnectAttempts });
        this.emit('reconnected', { attempt: this.reconnectAttempts });
      } catch (error) {
        logger.error('Reconnection failed', { attempt: this.reconnectAttempts, error });
        this.isReconnecting = false;
        // Schedule another reconnection attempt
        this.scheduleReconnection();
      }
    }, delay);
  }

  /**
   * Cancel any pending reconnection attempts
   */
  private cancelReconnection(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    this.isReconnecting = false;
  }

  private initializeSession() {
    // Configure the session
    this.send({
      type: 'session.update',
      session: {
        modalities: ['text', 'audio'],
        instructions: this.config.instructions || this.getDefaultInstructions(),
        voice: this.config.voice,
        input_audio_format: 'pcm16',
        output_audio_format: 'pcm16',
        input_audio_transcription: {
          model: 'whisper-1',
        },
        turn_detection: {
          type: 'server_vad',
          threshold: 0.5,
          prefix_padding_ms: 300,
          silence_duration_ms: 500,
        },
        tools: this.config.tools || [],
        temperature: this.config.temperature || 0.8,
      },
    });

    this.emit('connected');
  }

  private getDefaultInstructions(): string {
    return `You are JARVIS, an advanced AI voice assistant for Windows 11. You are helpful, efficient, and friendly.
You can control the computer through function calls, manage files, launch applications, and answer questions.
Keep responses concise and natural - you're having a conversation, not writing an essay.
When executing system commands, confirm actions and provide status updates.`;
  }

  private handleMessage(data: WebSocket.Data) {
    try {
      const event: RealtimeEvent = JSON.parse(data.toString());

      logger.debug('Realtime event received', { type: event.type });

      switch (event.type) {
        case 'session.created':
          this.sessionId = event.session.id;
          this.emit('session.created', event.session);
          break;

        case 'session.updated':
          this.emit('session.updated', event.session);
          break;

        case 'conversation.item.created':
          this.emit('conversation.item.created', event.item);
          break;

        case 'response.audio.delta':
          // Stream audio chunk to speaker
          this.emit('audio.delta', Buffer.from(event.delta, 'base64'));
          break;

        case 'response.audio.done':
          this.emit('audio.done');
          break;

        case 'response.text.delta':
          this.emit('text.delta', event.delta);
          break;

        case 'response.text.done':
          this.emit('text.done', event.text);
          break;

        case 'response.function_call_arguments.delta':
          this.emit('function.arguments.delta', event);
          break;

        case 'response.function_call_arguments.done':
          const functionCall: FunctionCall = {
            name: event.name,
            arguments: JSON.parse(event.arguments),
            callId: event.call_id,
          };
          this.emit('function.call', functionCall);
          break;

        case 'response.done':
          this.emit('response.done', event.response);
          break;

        case 'input_audio_buffer.speech_started':
          this.emit('speech.started');
          break;

        case 'input_audio_buffer.speech_stopped':
          this.emit('speech.stopped');
          break;

        case 'error':
          logger.error('Realtime API error event', event.error);
          this.emit('error', new Error(event.error.message));
          break;

        default:
          // Ignore other event types
          break;
      }
    } catch (error) {
      logger.error('Failed to parse Realtime message', { error });
    }
  }

  /**
   * Send audio input to the API
   */
  sendAudio(audioBuffer: Buffer) {
    if (!this.isConnected) {
      throw new Error('Not connected to Realtime API');
    }

    this.send({
      type: 'input_audio_buffer.append',
      audio: audioBuffer.toString('base64'),
    });
  }

  /**
   * Commit audio buffer and trigger response generation
   */
  commitAudio() {
    this.send({
      type: 'input_audio_buffer.commit',
    });

    this.send({
      type: 'response.create',
    });
  }

  /**
   * Send text input
   */
  sendText(text: string) {
    if (!this.isConnected) {
      throw new Error('Not connected to Realtime API');
    }

    this.send({
      type: 'conversation.item.create',
      item: {
        type: 'message',
        role: 'user',
        content: [
          {
            type: 'input_text',
            text,
          },
        ],
      },
    });

    this.send({
      type: 'response.create',
    });
  }

  /**
   * Send function call result
   */
  sendFunctionResult(callId: string, result: any) {
    this.send({
      type: 'conversation.item.create',
      item: {
        type: 'function_call_output',
        call_id: callId,
        output: JSON.stringify(result),
      },
    });

    this.send({
      type: 'response.create',
    });
  }

  /**
   * Cancel current response generation
   */
  cancelResponse() {
    this.send({
      type: 'response.cancel',
    });
  }

  private send(event: any) {
    if (!this.ws || !this.isConnected) {
      logger.warn('Cannot send - not connected');
      return;
    }

    try {
      this.ws.send(JSON.stringify(event));
    } catch (error) {
      logger.error('Failed to send message', { error });
    }
  }

  /**
   * Disconnect from the Realtime API
   * @param intentional - If true, will not attempt to reconnect
   */
  disconnect(intentional: boolean = true) {
    this.intentionalDisconnect = intentional;
    this.cancelReconnection();

    if (this.ws) {
      this.ws.close();
      this.ws = null;
      this.isConnected = false;
      this.sessionId = null;
    }
  }

  /**
   * Check if the client is currently connected
   */
  isActive(): boolean {
    return this.isConnected;
  }

  /**
   * Get reconnection status
   */
  getReconnectionStatus(): { isReconnecting: boolean; attempts: number; maxAttempts: number } {
    return {
      isReconnecting: this.isReconnecting,
      attempts: this.reconnectAttempts,
      maxAttempts: this.reconnectionConfig.maxAttempts,
    };
  }

  /**
   * Manually trigger a reconnection attempt
   */
  async reconnect(): Promise<void> {
    this.disconnect(false);
    this.reconnectAttempts = 0;
    await this.connect();
  }
}
