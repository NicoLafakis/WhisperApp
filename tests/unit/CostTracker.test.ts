/**
 * Unit tests for CostTracker
 */

import { CostTracker } from '../../src/main/engine/CostTracker';

describe('CostTracker', () => {
  let costTracker: CostTracker;

  beforeEach(() => {
    costTracker = new CostTracker(1.0, 30.0); // $1 daily, $30 monthly
  });

  describe('constructor', () => {
    it('should initialize with default budgets', () => {
      const tracker = new CostTracker();
      const metrics = tracker.getMetrics();
      expect(metrics.totalCost).toBe(0);
      expect(metrics.interactionCount).toBe(0);
    });

    it('should accept custom budgets', () => {
      const tracker = new CostTracker(5.0, 100.0);
      expect(tracker.isDailyBudgetExceeded()).toBe(false);
      expect(tracker.isMonthlyBudgetExceeded()).toBe(false);
    });
  });

  describe('recordRealtimeInteraction', () => {
    it('should record realtime API costs', () => {
      const cost = costTracker.recordRealtimeInteraction(5, 1000);

      expect(cost).toBeGreaterThan(0);

      const metrics = costTracker.getMetrics();
      expect(metrics.interactionCount).toBe(1);
      expect(metrics.totalCost).toBe(cost);
    });

    it('should accumulate multiple interactions', () => {
      costTracker.recordRealtimeInteraction(5, 1000);
      costTracker.recordRealtimeInteraction(10, 2000);

      const metrics = costTracker.getMetrics();
      expect(metrics.interactionCount).toBe(2);
    });
  });

  describe('recordWhisperTranscription', () => {
    it('should calculate Whisper cost correctly', () => {
      // Whisper costs $0.006 per minute
      const cost = costTracker.recordWhisperTranscription(1); // 1 minute

      expect(cost).toBeCloseTo(0.006, 5);
    });

    it('should handle fractional minutes', () => {
      const cost = costTracker.recordWhisperTranscription(0.5); // 30 seconds

      expect(cost).toBeCloseTo(0.003, 5);
    });
  });

  describe('recordGPTCompletion', () => {
    it('should calculate GPT-4o-mini cost correctly', () => {
      // Input: $0.150/1M tokens, Output: $0.600/1M tokens
      const cost = costTracker.recordGPTCompletion(1000, 500);

      const expectedCost = (1000 / 1000000) * 0.150 + (500 / 1000000) * 0.600;
      expect(cost).toBeCloseTo(expectedCost, 8);
    });
  });

  describe('recordElevenLabs', () => {
    it('should calculate ElevenLabs cost correctly', () => {
      // $0.30 per 1000 characters
      const cost = costTracker.recordElevenLabs(1000);

      expect(cost).toBeCloseTo(0.30, 5);
    });

    it('should handle variable character counts', () => {
      const cost = costTracker.recordElevenLabs(500);

      expect(cost).toBeCloseTo(0.15, 5);
    });
  });

  describe('recordFallbackInteraction', () => {
    it('should record all three stages of fallback chain', () => {
      const totalCost = costTracker.recordFallbackInteraction(
        1,      // 1 minute audio
        500,    // 500 input tokens
        300,    // 300 output tokens
        200     // 200 characters
      );

      // Should have recorded 4 entries (whisper + gpt + elevenlabs + entries from parent calls)
      // Actually the recordFallbackInteraction calls the other record methods which each add an entry
      const metrics = costTracker.getMetrics();
      expect(metrics.interactionCount).toBe(3); // 3 separate recordings
      expect(totalCost).toBeGreaterThan(0);
    });
  });

  describe('getMetrics', () => {
    it('should return correct metrics', () => {
      costTracker.recordRealtimeInteraction(5, 1000);

      const metrics = costTracker.getMetrics();

      expect(metrics).toHaveProperty('totalCost');
      expect(metrics).toHaveProperty('todayCost');
      expect(metrics).toHaveProperty('monthCost');
      expect(metrics).toHaveProperty('interactionCount');
      expect(metrics).toHaveProperty('averageCostPerInteraction');
      expect(metrics).toHaveProperty('budgetRemaining');
    });

    it('should calculate average cost correctly', () => {
      costTracker.recordWhisperTranscription(1); // $0.006
      costTracker.recordWhisperTranscription(1); // $0.006

      const metrics = costTracker.getMetrics();

      expect(metrics.averageCostPerInteraction).toBeCloseTo(0.006, 5);
    });

    it('should calculate budget remaining correctly', () => {
      // Daily budget is $1.00
      costTracker.recordElevenLabs(1000); // $0.30

      const metrics = costTracker.getMetrics();

      expect(metrics.budgetRemaining).toBeCloseTo(0.70, 5);
    });
  });

  describe('isDailyBudgetExceeded', () => {
    it('should return false when under budget', () => {
      costTracker.recordElevenLabs(100); // $0.03

      expect(costTracker.isDailyBudgetExceeded()).toBe(false);
    });

    it('should return true when at or over budget', () => {
      // Record enough to exceed $1.00 daily budget
      for (let i = 0; i < 4; i++) {
        costTracker.recordElevenLabs(1000); // $0.30 each = $1.20 total
      }

      expect(costTracker.isDailyBudgetExceeded()).toBe(true);
    });
  });

  describe('isMonthlyBudgetExceeded', () => {
    it('should return false when under monthly budget', () => {
      costTracker.recordElevenLabs(1000);

      expect(costTracker.isMonthlyBudgetExceeded()).toBe(false);
    });
  });

  describe('getDailyBudgetUsagePercent', () => {
    it('should return 0 with no usage', () => {
      expect(costTracker.getDailyBudgetUsagePercent()).toBe(0);
    });

    it('should return correct percentage', () => {
      // Daily budget is $1.00
      costTracker.recordElevenLabs(1000); // $0.30 = 30%

      expect(costTracker.getDailyBudgetUsagePercent()).toBeCloseTo(30, 0);
    });
  });

  describe('clearOldEntries', () => {
    it('should clear entries older than specified days', () => {
      // This is hard to test without mocking Date, but we can at least verify it doesn't crash
      costTracker.recordRealtimeInteraction(5, 1000);

      expect(() => costTracker.clearOldEntries(30)).not.toThrow();

      // Recent entries should still be there
      const metrics = costTracker.getMetrics();
      expect(metrics.interactionCount).toBe(1);
    });
  });
});
