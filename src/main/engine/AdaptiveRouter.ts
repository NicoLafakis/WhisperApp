/**
 * JARVIS Voice Agent - Adaptive Router
 * Intelligently switches between premium and efficient modes
 */

import { AgentMode, RoutingDecision } from '../../shared/types';
import { CostTracker } from './CostTracker';
import { logger } from '../../shared/utils/logger';

interface RoutingConfig {
  defaultMode: AgentMode;
  peakHoursStart: number;
  peakHoursEnd: number;
  budgetThreshold: number; // Switch to efficient mode when daily budget usage exceeds this %
}

export class AdaptiveRouter {
  private costTracker: CostTracker;
  private config: RoutingConfig;
  private forcedMode: AgentMode | null = null;

  constructor(costTracker: CostTracker, config: RoutingConfig) {
    this.costTracker = costTracker;
    this.config = config;
  }

  /**
   * Decide which mode to use for the next interaction
   */
  route(interactionType?: string): RoutingDecision {
    // If user has forced a specific mode, use that
    if (this.forcedMode) {
      return {
        mode: this.forcedMode,
        reason: 'user_preference',
        estimatedCost: this.estimateCost(this.forcedMode),
        estimatedLatency: this.estimateLatency(this.forcedMode),
      };
    }

    // Check budget constraints
    const budgetUsage = this.costTracker.getDailyBudgetUsagePercent();
    if (budgetUsage >= this.config.budgetThreshold) {
      logger.info('Switching to efficient mode due to budget threshold', {
        budgetUsage: budgetUsage.toFixed(1) + '%',
      });
      return {
        mode: 'efficient',
        reason: 'cost_limit',
        estimatedCost: this.estimateCost('efficient'),
        estimatedLatency: this.estimateLatency('efficient'),
      };
    }

    // Check time of day (use efficient mode outside peak hours)
    const hour = new Date().getHours();
    const isPeakHours = hour >= this.config.peakHoursStart && hour < this.config.peakHoursEnd;

    if (!isPeakHours) {
      return {
        mode: 'efficient',
        reason: 'time_of_day',
        estimatedCost: this.estimateCost('efficient'),
        estimatedLatency: this.estimateLatency('efficient'),
      };
    }

    // Check interaction type (simple queries can use efficient mode)
    if (interactionType === 'simple') {
      return {
        mode: 'efficient',
        reason: 'interaction_type',
        estimatedCost: this.estimateCost('efficient'),
        estimatedLatency: this.estimateLatency('efficient'),
      };
    }

    // Default to configured mode
    return {
      mode: this.config.defaultMode,
      reason: 'time_of_day',
      estimatedCost: this.estimateCost(this.config.defaultMode),
      estimatedLatency: this.estimateLatency(this.config.defaultMode),
    };
  }

  private estimateCost(mode: AgentMode): number {
    if (mode === 'premium') {
      return 0.12; // Average realtime API cost per interaction
    } else {
      return 0.004; // Average fallback chain cost
    }
  }

  private estimateLatency(mode: AgentMode): number {
    if (mode === 'premium') {
      return 500; // 300-800ms average
    } else {
      return 2000; // 1.5-2.5s average
    }
  }

  /**
   * Force a specific mode (overrides automatic routing)
   */
  setForcedMode(mode: AgentMode | null) {
    this.forcedMode = mode;
    logger.info('Forced mode set', { mode });
  }

  /**
   * Get current routing statistics
   */
  getStats() {
    const metrics = this.costTracker.getMetrics();
    const budgetUsage = this.costTracker.getDailyBudgetUsagePercent();

    return {
      budgetUsage,
      todayCost: metrics.todayCost,
      interactionCount: metrics.interactionCount,
      averageCost: metrics.averageCostPerInteraction,
      forcedMode: this.forcedMode,
    };
  }
}
