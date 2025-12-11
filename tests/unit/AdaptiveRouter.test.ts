/**
 * Unit tests for AdaptiveRouter
 */

import { AdaptiveRouter } from '../../src/main/engine/AdaptiveRouter';
import { CostTracker } from '../../src/main/engine/CostTracker';

describe('AdaptiveRouter', () => {
  let costTracker: CostTracker;
  let router: AdaptiveRouter;

  const defaultConfig = {
    defaultMode: 'premium' as const,
    peakHoursStart: 9,
    peakHoursEnd: 17,
    budgetThreshold: 50, // Switch at 50% budget usage
    dailyBudget: 1.0,
    monthlyBudget: 30.0,
  };

  beforeEach(() => {
    jest.restoreAllMocks();
    costTracker = new CostTracker(1.0, 30.0);
    router = new AdaptiveRouter(costTracker, defaultConfig);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('route', () => {
    it('should return a routing decision', () => {
      const decision = router.route();

      expect(decision).toHaveProperty('mode');
      expect(decision).toHaveProperty('reason');
      expect(decision).toHaveProperty('estimatedCost');
      expect(decision).toHaveProperty('estimatedLatency');
    });

    it('should use forced mode when set', () => {
      router.setForcedMode('efficient');

      const decision = router.route();

      expect(decision.mode).toBe('efficient');
      expect(decision.reason).toBe('user_preference');
    });

    it('should switch to efficient mode when budget threshold exceeded', () => {
      // Use up 60% of budget ($0.60 of $1.00)
      for (let i = 0; i < 2; i++) {
        costTracker.recordElevenLabs(1000); // $0.30 each
      }

      const decision = router.route();

      expect(decision.mode).toBe('efficient');
      expect(decision.reason).toBe('cost_limit');
    });

    it('should use efficient mode for simple interaction types during peak hours', () => {
      // Mock peak hours (12 PM)
      jest.spyOn(Date.prototype, 'getHours').mockReturnValue(12);

      const decision = router.route('simple');

      expect(decision.mode).toBe('efficient');
      expect(decision.reason).toBe('interaction_type');
    });
  });

  describe('time-based routing', () => {
    it('should use efficient mode outside peak hours', () => {
      // Mock outside peak hours (8 AM, before 9 AM start)
      jest.spyOn(Date.prototype, 'getHours').mockReturnValue(8);

      const decision = router.route();

      expect(decision.mode).toBe('efficient');
      expect(decision.reason).toBe('time_of_day');
    });

    it('should use default mode during peak hours with available budget', () => {
      // Mock during peak hours (12 PM)
      jest.spyOn(Date.prototype, 'getHours').mockReturnValue(12);

      const decision = router.route();

      // Should use default mode (premium) during peak hours
      expect(decision.mode).toBe('premium');
    });
  });

  describe('setForcedMode', () => {
    it('should set forced mode to premium', () => {
      router.setForcedMode('premium');

      const decision = router.route();
      expect(decision.mode).toBe('premium');
    });

    it('should set forced mode to efficient', () => {
      router.setForcedMode('efficient');

      const decision = router.route();
      expect(decision.mode).toBe('efficient');
    });

    it('should clear forced mode when set to null', () => {
      router.setForcedMode('efficient');
      router.setForcedMode(null);

      // Mock peak hours so default mode would be used
      jest.spyOn(Date.prototype, 'getHours').mockReturnValue(12);

      const decision = router.route();
      // Should go back to automatic routing
      expect(decision.reason).not.toBe('user_preference');
    });
  });

  describe('getStats', () => {
    it('should return current statistics', () => {
      costTracker.recordRealtimeInteraction(5, 1000);

      const stats = router.getStats();

      expect(stats).toHaveProperty('budgetUsage');
      expect(stats).toHaveProperty('todayCost');
      expect(stats).toHaveProperty('interactionCount');
      expect(stats).toHaveProperty('averageCost');
      expect(stats).toHaveProperty('forcedMode');

      expect(stats.interactionCount).toBe(1);
    });

    it('should reflect forced mode in stats', () => {
      router.setForcedMode('efficient');

      const stats = router.getStats();

      expect(stats.forcedMode).toBe('efficient');
    });
  });

  describe('cost estimation', () => {
    it('should estimate higher cost for premium mode', () => {
      router.setForcedMode('premium');
      const premiumDecision = router.route();

      router.setForcedMode('efficient');
      const efficientDecision = router.route();

      expect(premiumDecision.estimatedCost).toBeGreaterThan(efficientDecision.estimatedCost);
    });

    it('should estimate lower latency for premium mode', () => {
      router.setForcedMode('premium');
      const premiumDecision = router.route();

      router.setForcedMode('efficient');
      const efficientDecision = router.route();

      expect(premiumDecision.estimatedLatency).toBeLessThan(efficientDecision.estimatedLatency);
    });
  });
});
