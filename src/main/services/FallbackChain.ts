/**
 * JARVIS Voice Agent - Fallback Chain
 * Whisper → GPT-4o-mini → ElevenLabs pipeline for cost-efficient mode
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
}

export class FallbackChain extends EventEmitter {
  private openai: OpenAI;
  private elevenlabs: ElevenLabsClient;
  private config: FallbackChainConfig;
  private conversationHistory: Array<{ role: string; content: string }> = [];

  constructor(config: FallbackChainConfig) {
    super();
    this.config = config;

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
   * Process a complete interaction through the fallback chain
   * @param audioBuffer - Audio buffer in 16kHz PCM format
   * @returns Audio response as a buffer
   */
  async processAudio(audioBuffer: Buffer): Promise<{ audioBuffer: Buffer; text: string; cost: number }> {
    try {
      // Step 1: Whisper transcription
      this.emit('stage', 'transcribing');
      const transcription = await this.transcribeAudio(audioBuffer);
      logger.info('Transcription completed', { text: transcription });
      this.emit('transcription', transcription);

      // Step 2: GPT-4o-mini reasoning
      this.emit('stage', 'reasoning');
      const response = await this.generateResponse(transcription);
      logger.info('Response generated', { text: response.text });
      this.emit('response', response.text);

      // Step 3: ElevenLabs TTS
      this.emit('stage', 'synthesizing');
      const audioResponse = await this.synthesizeSpeech(response.text);
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
      fs.unlinkSync(tempFile);

      return transcription.text;

    } catch (error) {
      // Clean up temp file on error
      if (fs.existsSync(tempFile)) {
        fs.unlinkSync(tempFile);
      }
      throw error;
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
    const audioStream = await this.elevenlabs.generate({
      voice: this.config.elevenlabsVoiceId,
      text: text,
      model_id: 'eleven_monolingual_v1',
    });

    // Convert stream to buffer
    const chunks: Buffer[] = [];

    for await (const chunk of audioStream) {
      chunks.push(chunk);
    }

    return Buffer.concat(chunks);
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
}
