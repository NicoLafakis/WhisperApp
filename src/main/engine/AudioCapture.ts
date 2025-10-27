/**
 * JARVIS Voice Agent - Audio Capture Module
 * Captures audio at 16kHz mono PCM format
 */

import { EventEmitter } from 'events';
import * as record from 'node-record-lpcm16';
import { AudioConfig, AudioBuffer } from '../../shared/types';
import { logger } from '../../shared/utils/logger';

export class AudioCapture extends EventEmitter {
  private recording: any = null;
  private isRecording: boolean = false;
  private audioConfig: AudioConfig;
  private audioChunks: Buffer[] = [];

  constructor(config: AudioConfig) {
    super();
    this.audioConfig = config;
  }

  start() {
    if (this.isRecording) {
      logger.warn('Audio capture already running');
      return;
    }

    try {
      this.recording = record.record({
        sampleRate: this.audioConfig.sampleRate,
        channels: this.audioConfig.channels,
        audioType: 'raw',
        recorder: 'sox', // Use sox on Linux/Windows
        silence: '2.0', // Silence threshold
        threshold: 0.5,
      });

      this.recording.stream()
        .on('data', (chunk: Buffer) => {
          this.handleAudioData(chunk);
        })
        .on('error', (err: Error) => {
          logger.error('Audio capture error', { error: err.message });
          this.emit('error', err);
        });

      this.isRecording = true;
      logger.info('Audio capture started', {
        sampleRate: this.audioConfig.sampleRate,
        channels: this.audioConfig.channels,
      });

      this.emit('started');
    } catch (error) {
      logger.error('Failed to start audio capture', { error });
      throw error;
    }
  }

  stop() {
    if (!this.isRecording || !this.recording) {
      return;
    }

    try {
      record.stop();
      this.isRecording = false;
      this.recording = null;
      logger.info('Audio capture stopped');
      this.emit('stopped');
    } catch (error) {
      logger.error('Failed to stop audio capture', { error });
    }
  }

  private handleAudioData(chunk: Buffer) {
    const audioBuffer: AudioBuffer = {
      data: chunk,
      timestamp: Date.now(),
      duration: chunk.length / (this.audioConfig.sampleRate * 2), // 16-bit = 2 bytes per sample
    };

    this.audioChunks.push(chunk);
    this.emit('audio', audioBuffer);
  }

  getRecordedAudio(): Buffer {
    return Buffer.concat(this.audioChunks);
  }

  clearBuffer() {
    this.audioChunks = [];
  }

  isActive(): boolean {
    return this.isRecording;
  }
}
