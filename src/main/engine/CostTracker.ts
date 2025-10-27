/**
 * JARVIS Voice Agent - Cost Tracking Module
 * Monitors API usage costs and budget limits
 */

import { CostMetrics, AgentMode } from '../../shared/types';
import { logger } from '../../shared/utils/logger';

interface CostEntry {
  timestamp: number;
  mode: AgentMode;
  cost: number;
  tokens?: number;
  audioSeconds?: number;
}

export class CostTracker {
  private entries: CostEntry[] = [];
  private dailyBudget: number;
  private monthlyBudget: number;

  // Pricing (as of Oct 2024)
  private readonly PRICING = {
    // Realtime API (per 1M tokens)
    realtimeInput: 5.00,    // Text input
    realtimeOutput: 20.00,  // Text output
    realtimeAudioInput: 100.00,   // Audio input
    realtimeAudioOutput: 200.00,  // Audio output

    // Whisper (per minute)
    whisper: 0.006,

    // GPT-4o-mini (per 1M tokens)
    gpt4oMiniInput: 0.150,
    gpt4oMiniOutput: 0.600,

    // ElevenLabs TTS (per 1000 characters)
    elevenlabs: 0.30,
  };

  constructor(dailyBudget: number = 1.0, monthlyBudget: number = 30.0) {
    this.dailyBudget = dailyBudget;
    this.monthlyBudget = monthlyBudget;
  }

  /**
   * Record a Realtime API interaction
   */
  recordRealtimeInteraction(audioSeconds: number, estimatedTokens: number = 1000) {
    // Estimate cost for realtime interaction
    // Assuming 15 seconds average audio, ~500 input tokens, ~500 output tokens
    const inputTokens = estimatedTokens / 2;
    const outputTokens = estimatedTokens / 2;

    const cost =
      (inputTokens / 1000000) * this.PRICING.realtimeAudioInput +
      (outputTokens / 1000000) * this.PRICING.realtimeAudioOutput;

    this.addEntry({
      timestamp: Date.now(),
      mode: 'premium',
      cost,
      audioSeconds,
      tokens: estimatedTokens,
    });

    logger.info('Realtime interaction recorded', {
      cost: cost.toFixed(4),
      audioSeconds,
      tokens: estimatedTokens,
    });

    return cost;
  }

  /**
   * Record a Whisper transcription
   */
  recordWhisperTranscription(audioMinutes: number) {
    const cost = audioMinutes * this.PRICING.whisper;

    this.addEntry({
      timestamp: Date.now(),
      mode: 'efficient',
      cost,
      audioSeconds: audioMinutes * 60,
    });

    return cost;
  }

  /**
   * Record a GPT-4o-mini completion
   */
  recordGPTCompletion(inputTokens: number, outputTokens: number) {
    const cost =
      (inputTokens / 1000000) * this.PRICING.gpt4oMiniInput +
      (outputTokens / 1000000) * this.PRICING.gpt4oMiniOutput;

    this.addEntry({
      timestamp: Date.now(),
      mode: 'efficient',
      cost,
      tokens: inputTokens + outputTokens,
    });

    return cost;
  }

  /**
   * Record an ElevenLabs TTS generation
   */
  recordElevenLabs(characters: number) {
    const cost = (characters / 1000) * this.PRICING.elevenlabs;

    this.addEntry({
      timestamp: Date.now(),
      mode: 'efficient',
      cost,
    });

    return cost;
  }

  /**
   * Record a complete fallback chain interaction
   */
  recordFallbackInteraction(
    audioMinutes: number,
    inputTokens: number,
    outputTokens: number,
    elevenlabsCharacters: number
  ) {
    const whisperCost = this.recordWhisperTranscription(audioMinutes);
    const gptCost = this.recordGPTCompletion(inputTokens, outputTokens);
    const elevenlabsCost = this.recordElevenLabs(elevenlabsCharacters);

    const totalCost = whisperCost + gptCost + elevenlabsCost;

    logger.info('Fallback interaction recorded', {
      totalCost: totalCost.toFixed(4),
      whisper: whisperCost.toFixed(4),
      gpt: gptCost.toFixed(4),
      elevenlabs: elevenlabsCost.toFixed(4),
    });

    return totalCost;
  }

  private addEntry(entry: CostEntry) {
    this.entries.push(entry);
  }

  getMetrics(): CostMetrics {
    const now = Date.now();
    const oneDayAgo = now - 24 * 60 * 60 * 1000;
    const oneMonthAgo = now - 30 * 24 * 60 * 60 * 1000;

    const todayEntries = this.entries.filter(e => e.timestamp >= oneDayAgo);
    const monthEntries = this.entries.filter(e => e.timestamp >= oneMonthAgo);

    const todayCost = todayEntries.reduce((sum, e) => sum + e.cost, 0);
    const monthCost = monthEntries.reduce((sum, e) => sum + e.cost, 0);
    const totalCost = this.entries.reduce((sum, e) => sum + e.cost, 0);

    return {
      totalCost,
      todayCost,
      monthCost,
      interactionCount: this.entries.length,
      averageCostPerInteraction: this.entries.length > 0 ? totalCost / this.entries.length : 0,
      budgetRemaining: this.dailyBudget - todayCost,
    };
  }

  isDailyBudgetExceeded(): boolean {
    const metrics = this.getMetrics();
    return metrics.todayCost >= this.dailyBudget;
  }

  isMonthlyBudgetExceeded(): boolean {
    const metrics = this.getMetrics();
    return metrics.monthCost >= this.monthlyBudget;
  }

  getDailyBudgetUsagePercent(): number {
    const metrics = this.getMetrics();
    return (metrics.todayCost / this.dailyBudget) * 100;
  }

  clearOldEntries(daysToKeep: number = 30) {
    const cutoff = Date.now() - daysToKeep * 24 * 60 * 60 * 1000;
    this.entries = this.entries.filter(e => e.timestamp >= cutoff);
    logger.info(`Cleared cost entries older than ${daysToKeep} days`);
  }
}
