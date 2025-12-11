/**
 * JARVIS Voice Agent - Fallback Chain
 * Whisper → GPT-4o-mini → ElevenLabs pipeline for cost-efficient mode
 * Includes retry mechanisms with exponential backoff for API resilience
 */

import { EventEmitter } from 'events';
import OpenAI from 'openai';
import { ElevenLabsClient } from 'elevenlabs';
import { Readable } from 'stream';
import * as fs from 'fs';
import * as path from 'path';
import { logger } from '../../shared/utils/logger';
import { FunctionDefinition } from '../../shared/types';

export interface FallbackChainConfig {
  openaiApiKey: string;
  elevenlabsApiKey: string;
  elevenlabsVoiceId: string;
  systemPrompt?: string;
  tools?: FunctionDefinition[];
  retryConfig?: Partial<RetryConfig>;
}

interface RetryConfig {
  maxRetries: number;
  initialDelayMs: number;
  maxDelayMs: number;
  backoffMultiplier: number;
  retryableStatusCodes: number[];
}

const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxRetries: 3,
  initialDelayMs: 1000,
  maxDelayMs: 10000,
  backoffMultiplier: 2,
  retryableStatusCodes: [408, 429, 500, 502, 503, 504],
};

interface RetryableError extends Error {
  status?: number;
  code?: string;
}

export class FallbackChain extends EventEmitter {
  private openai: OpenAI;
  private elevenlabs: ElevenLabsClient;
  private config: FallbackChainConfig;
  private retryConfig: RetryConfig;
  private conversationHistory: Array<{ role: string; content: string }> = [];

  constructor(config: FallbackChainConfig) {
    super();
    this.config = config;
    this.retryConfig = { ...DEFAULT_RETRY_CONFIG, ...config.retryConfig };

    this.openai = new OpenAI({
      apiKey: config.openaiApiKey,
    });

    this.elevenlabs = new ElevenLabsClient({
      apiKey: config.elevenlabsApiKey,
    });

    // Initialize conversation with system prompt
    if (config.systemPrompt) {
      this.conversationHistory.push({
        role: 'system',
        content: config.systemPrompt,
      });
    }
  }

  /**
   * Execute an async operation with retry logic
   */
  private async withRetry<T>(
    operation: () => Promise<T>,
    operationName: string
  ): Promise<T> {
    let lastError: Error | null = null;

    for (let attempt = 0; attempt <= this.retryConfig.maxRetries; attempt++) {
      try {
        if (attempt > 0) {
          const delay = this.calculateRetryDelay(attempt);
          logger.info(`Retrying ${operationName}`, {
            attempt,
            maxRetries: this.retryConfig.maxRetries,
            delayMs: delay,
          });
          this.emit('retry', { operation: operationName, attempt, delay });
          await this.sleep(delay);
        }

        return await operation();
      } catch (error: any) {
        lastError = error;

        if (!this.isRetryableError(error)) {
          logger.error(`Non-retryable error in ${operationName}`, {
            error: error.message,
            status: error.status,
            code: error.code,
          });
          throw error;
        }

        logger.warn(`Retryable error in ${operationName}`, {
          attempt,
          error: error.message,
          status: error.status,
          code: error.code,
        });

        if (attempt === this.retryConfig.maxRetries) {
          logger.error(`Max retries reached for ${operationName}`, {
            attempts: attempt + 1,
            lastError: error.message,
          });
          throw error;
        }
      }
    }

    // Should never reach here, but TypeScript needs this
    throw lastError || new Error(`Unknown error in ${operationName}`);
  }

  /**
   * Check if an error is retryable
   */
  private isRetryableError(error: RetryableError): boolean {
    // Network errors
    if (error.code === 'ECONNRESET' || error.code === 'ETIMEDOUT' || error.code === 'ENOTFOUND') {
      return true;
    }

    // Rate limiting
    if (error.status === 429) {
      return true;
    }

    // Server errors
    if (error.status && this.retryConfig.retryableStatusCodes.includes(error.status)) {
      return true;
    }

    // OpenAI specific errors
    if (error.message?.includes('overloaded') || error.message?.includes('rate limit')) {
      return true;
    }

    return false;
  }

  /**
   * Calculate delay for retry attempt with exponential backoff
   */
  private calculateRetryDelay(attempt: number): number {
    const delay = this.retryConfig.initialDelayMs * Math.pow(this.retryConfig.backoffMultiplier, attempt - 1);
    // Add jitter (±20%)
    const jitter = delay * 0.2 * (Math.random() * 2 - 1);
    return Math.min(delay + jitter, this.retryConfig.maxDelayMs);
  }

  /**
   * Sleep for a given number of milliseconds
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Process a complete interaction through the fallback chain
   * @param audioBuffer - Audio buffer in 16kHz PCM format
   * @returns Audio response as a buffer
   */
  async processAudio(audioBuffer: Buffer): Promise<{ audioBuffer: Buffer; text: string; cost: number }> {
    try {
      // Step 1: Whisper transcription (with retry)
      this.emit('stage', 'transcribing');
      const transcription = await this.withRetry(
        () => this.transcribeAudio(audioBuffer),
        'whisper-transcription'
      );
      logger.info('Transcription completed', { text: transcription });
      this.emit('transcription', transcription);

      // Step 2: GPT-4o-mini reasoning (with retry)
      this.emit('stage', 'reasoning');
      const response = await this.withRetry(
        () => this.generateResponse(transcription),
        'gpt-completion'
      );
      logger.info('Response generated', { text: response.text });
      this.emit('response', response.text);

      // Step 3: ElevenLabs TTS (with retry)
      this.emit('stage', 'synthesizing');
      const audioResponse = await this.withRetry(
        () => this.synthesizeSpeech(response.text),
        'elevenlabs-tts'
      );
      logger.info('Speech synthesized', { bytes: audioResponse.length });
      this.emit('audio', audioResponse);

      // Calculate total cost
      const cost = this.calculateCost(audioBuffer, response);

      return {
        audioBuffer: audioResponse,
        text: response.text,
        cost,
      };

    } catch (error) {
      logger.error('Fallback chain error', { error });
      this.emit('error', error);
      throw error;
    }
  }

  /**
   * Step 1: Transcribe audio using Whisper
   */
  private async transcribeAudio(audioBuffer: Buffer): Promise<string> {
    // Save audio buffer to temporary WAV file
    const tempDir = path.join(process.cwd(), 'temp-audio');
    if (!fs.existsSync(tempDir)) {
      fs.mkdirSync(tempDir, { recursive: true });
    }

    const tempFile = path.join(tempDir, `temp-${Date.now()}.wav`);

    // Write WAV header for 16kHz mono PCM
    const wavHeader = this.createWavHeader(audioBuffer.length, 16000, 1, 16);
    const wavBuffer = Buffer.concat([wavHeader, audioBuffer]);
    fs.writeFileSync(tempFile, wavBuffer);

    try {
      const transcription = await this.openai.audio.transcriptions.create({
        file: fs.createReadStream(tempFile),
        model: 'whisper-1',
        language: 'en',
      });

      // Clean up temp file
      this.cleanupTempFile(tempFile);

      return transcription.text;

    } catch (error) {
      // Clean up temp file on error
      this.cleanupTempFile(tempFile);
      throw error;
    }
  }

  /**
   * Safely clean up a temporary file
   */
  private cleanupTempFile(filePath: string): void {
    try {
      if (fs.existsSync(filePath)) {
        fs.unlinkSync(filePath);
      }
    } catch (error) {
      logger.warn('Failed to clean up temp file', { filePath, error });
    }
  }

  /**
   * Step 2: Generate response using GPT-4o-mini
   */
  private async generateResponse(userMessage: string): Promise<{ text: string; tokensUsed: { input: number; output: number } }> {
    // Add user message to history
    this.conversationHistory.push({
      role: 'user',
      content: userMessage,
    });

    const completion = await this.openai.chat.completions.create({
      model: 'gpt-4o-mini',
      messages: this.conversationHistory as any,
      temperature: 0.8,
      max_tokens: 500,
      tools: this.config.tools as any,
    });

    const assistantMessage = completion.choices[0].message;
    const responseText = assistantMessage.content || '';

    // Add assistant response to history
    this.conversationHistory.push({
      role: 'assistant',
      content: responseText,
    });

    // Handle function calls if present
    if (assistantMessage.tool_calls && assistantMessage.tool_calls.length > 0) {
      this.emit('function.calls', assistantMessage.tool_calls);
    }

    // Trim conversation history to last 10 messages (to control context)
    if (this.conversationHistory.length > 10) {
      // Keep system message if present
      const systemMsg = this.conversationHistory[0].role === 'system' ? this.conversationHistory[0] : null;
      this.conversationHistory = systemMsg
        ? [systemMsg, ...this.conversationHistory.slice(-9)]
        : this.conversationHistory.slice(-10);
    }

    return {
      text: responseText,
      tokensUsed: {
        input: completion.usage?.prompt_tokens || 0,
        output: completion.usage?.completion_tokens || 0,
      },
    };
  }

  /**
   * Step 3: Synthesize speech using ElevenLabs
   */
  private async synthesizeSpeech(text: string): Promise<Buffer> {
    // Handle empty text gracefully
    if (!text || text.trim().length === 0) {
      logger.warn('Empty text provided for speech synthesis, returning silence');
      return Buffer.alloc(0);
    }

    const audioStream = await this.elevenlabs.generate({
      voice: this.config.elevenlabsVoiceId,
      text: text,
      model_id: 'eleven_monolingual_v1',
    });

    // Convert stream to buffer with timeout
    const chunks: Buffer[] = [];
    const timeoutPromise = new Promise<never>((_, reject) => {
      setTimeout(() => reject(new Error('Speech synthesis timeout')), 30000);
    });

    const streamPromise = (async () => {
      for await (const chunk of audioStream) {
        chunks.push(chunk);
      }
      return Buffer.concat(chunks);
    })();

    return Promise.race([streamPromise, timeoutPromise]);
  }

  /**
   * Create WAV header for PCM audio
   */
  private createWavHeader(dataLength: number, sampleRate: number, channels: number, bitsPerSample: number): Buffer {
    const header = Buffer.alloc(44);

    // RIFF header
    header.write('RIFF', 0);
    header.writeUInt32LE(36 + dataLength, 4);
    header.write('WAVE', 8);

    // fmt chunk
    header.write('fmt ', 12);
    header.writeUInt32LE(16, 16); // fmt chunk size
    header.writeUInt16LE(1, 20); // PCM format
    header.writeUInt16LE(channels, 22);
    header.writeUInt32LE(sampleRate, 24);
    header.writeUInt32LE(sampleRate * channels * (bitsPerSample / 8), 28); // byte rate
    header.writeUInt16LE(channels * (bitsPerSample / 8), 32); // block align
    header.writeUInt16LE(bitsPerSample, 34);

    // data chunk
    header.write('data', 36);
    header.writeUInt32LE(dataLength, 40);

    return header;
  }

  /**
   * Calculate cost of the interaction
   */
  private calculateCost(audioBuffer: Buffer, response: { text: string; tokensUsed: { input: number; output: number } }): number {
    // Whisper: $0.006/minute
    const audioMinutes = (audioBuffer.length / (16000 * 2)) / 60; // 16kHz, 16-bit (2 bytes)
    const whisperCost = audioMinutes * 0.006;

    // GPT-4o-mini: $0.150/1M input tokens, $0.600/1M output tokens
    const gptCost =
      (response.tokensUsed.input / 1000000) * 0.150 +
      (response.tokensUsed.output / 1000000) * 0.600;

    // ElevenLabs: ~$0.30/1000 characters (average pricing)
    const characterCount = response.text.length;
    const elevenlabsCost = (characterCount / 1000) * 0.30;

    const totalCost = whisperCost + gptCost + elevenlabsCost;

    logger.info('Fallback chain cost breakdown', {
      whisper: whisperCost.toFixed(4),
      gpt: gptCost.toFixed(4),
      elevenlabs: elevenlabsCost.toFixed(4),
      total: totalCost.toFixed(4),
    });

    return totalCost;
  }

  /**
   * Clear conversation history
   */
  clearHistory() {
    const systemMsg = this.conversationHistory[0]?.role === 'system' ? this.conversationHistory[0] : null;
    this.conversationHistory = systemMsg ? [systemMsg] : [];
    logger.info('Conversation history cleared');
  }

  /**
   * Get conversation history
   */
  getHistory() {
    return [...this.conversationHistory];
  }

  /**
   * Get retry configuration
   */
  getRetryConfig(): RetryConfig {
    return { ...this.retryConfig };
  }

  /**
   * Update retry configuration
   */
  setRetryConfig(config: Partial<RetryConfig>): void {
    this.retryConfig = { ...this.retryConfig, ...config };
    logger.info('Retry configuration updated', { config: this.retryConfig });
  }
}
