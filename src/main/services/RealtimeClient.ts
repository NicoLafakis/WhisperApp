/**
 * JARVIS Voice Agent - OpenAI Realtime API Client
 * WebRTC-based speech-to-speech communication
 */

import { EventEmitter } from 'events';
import WebSocket from 'ws';
import { RealtimeConfig, FunctionDefinition, FunctionCall } from '../../shared/types';
import { logger } from '../../shared/utils/logger';

interface RealtimeEvent {
  type: string;
  [key: string]: any;
}

export class RealtimeClient extends EventEmitter {
  private ws: WebSocket | null = null;
  private config: RealtimeConfig;
  private isConnected: boolean = false;
  private sessionId: string | null = null;

  constructor(config: RealtimeConfig) {
    super();
    this.config = config;
  }

  async connect() {
    if (this.isConnected) {
      logger.warn('Realtime client already connected');
      return;
    }

    const url = 'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01';

    try {
      this.ws = new WebSocket(url, {
        headers: {
          'Authorization': `Bearer ${this.config.apiKey}`,
          'OpenAI-Beta': 'realtime=v1',
        },
      });

      this.ws.on('open', () => {
        logger.info('Realtime API connected');
        this.isConnected = true;
        this.initializeSession();
      });

      this.ws.on('message', (data: WebSocket.Data) => {
        this.handleMessage(data);
      });

      this.ws.on('error', (error) => {
        logger.error('Realtime API error', { error: error.message });
        this.emit('error', error);
      });

      this.ws.on('close', () => {
        logger.info('Realtime API disconnected');
        this.isConnected = false;
        this.emit('disconnected');
      });

    } catch (error) {
      logger.error('Failed to connect to Realtime API', { error });
      throw error;
    }
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

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
      this.isConnected = false;
      this.sessionId = null;
    }
  }

  isActive(): boolean {
    return this.isConnected;
  }
}
