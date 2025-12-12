/**
 * JARVIS Voice Agent - Type Definitions
 */

// ==================== Audio Types ====================

export interface AudioConfig {
  sampleRate: number;
  channels: number;
  bitDepth: number;
}

export interface AudioBuffer {
  data: Buffer;
  timestamp: number;
  duration: number;
}

// ==================== Mode & Routing Types ====================

export type AgentMode = 'premium' | 'efficient';

export interface RoutingDecision {
  mode: AgentMode;
  reason: 'cost_limit' | 'high_latency_ok' | 'time_of_day' | 'interaction_type' | 'user_preference';
  estimatedCost: number;
  estimatedLatency: number;
}

export interface CostMetrics {
  totalCost: number;
  todayCost: number;
  monthCost: number;
  interactionCount: number;
  averageCostPerInteraction: number;
  budgetRemaining: number;
}

// ==================== Agent State Types ====================

export type AgentStatus = 'idle' | 'listening' | 'thinking' | 'speaking' | 'executing' | 'error';

export interface AgentState {
  status: AgentStatus;
  mode: AgentMode;
  isWakeWordActive: boolean;
  currentInteraction: string | null;
  metrics: CostMetrics;
}

// ==================== Function Calling Types ====================

export interface FunctionDefinition {
  name: string;
  description: string;
  parameters: {
    type: 'object';
    properties: Record<string, any>;
    required?: string[];
  };
}

export interface FunctionCall {
  name: string;
  arguments: Record<string, any>;
  callId: string;
}

export interface FunctionResult {
  callId: string;
  result: any;
  error?: string;
  executionTime: number;
}

// ==================== Conversation Types ====================

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'function';
  content: string;
  timestamp: number;
  audioUrl?: string;
  functionCall?: FunctionCall;
  functionResult?: FunctionResult;
}

export interface Conversation {
  id: string;
  messages: Message[];
  startTime: number;
  endTime?: number;
  totalCost: number;
}

// ==================== OpenAI API Types ====================

export interface RealtimeConfig {
  apiKey: string;
  model: 'gpt-4o-realtime-preview-2024-10-01';
  voice: 'alloy' | 'echo' | 'fable' | 'onyx' | 'nova' | 'shimmer';
  instructions?: string;
  tools?: FunctionDefinition[];
  temperature?: number;
}

export interface WhisperConfig {
  apiKey: string;
  model: 'whisper-1';
  language?: string;
  temperature?: number;
}

export interface TTSConfig {
  apiKey: string;
  model: 'tts-1' | 'tts-1-hd';
  voice: 'alloy' | 'echo' | 'fable' | 'onyx' | 'nova' | 'shimmer';
  speed?: number;
}

export interface GPTConfig {
  apiKey: string;
  model: 'gpt-4o-mini';
  temperature?: number;
  maxTokens?: number;
}

// ==================== Configuration Types ====================

export interface AppConfig {
  openai: {
    apiKey: string;
  };
  elevenlabs: {
    apiKey: string;
    voiceId: string;
  };
  audio: AudioConfig;
  wakeWord: {
    keyword: string;
    sensitivity: number;
  };
  routing: {
    defaultMode: AgentMode;
    dailyBudget: number;
    monthlyBudget: number;
    peakHoursStart: number;
    peakHoursEnd: number;
    budgetThreshold: number;
  };
  voice: {
    name: 'alloy' | 'echo' | 'fable' | 'onyx' | 'nova' | 'shimmer';
    speed: number;
  };
  security: {
    requireConfirmation: string[];
    blocked: string[];
  };
}

// ==================== Event Types ====================

export interface IPCEvents {
  // Main -> Renderer
  'agent:status-changed': AgentState;
  'agent:message': Message;
  'agent:error': { message: string; code?: string };
  'cost:updated': CostMetrics;

  // Renderer -> Main
  'agent:start': void;
  'agent:stop': void;
  'agent:send-message': string;
  'config:get': void;
  'config:update': Partial<AppConfig>;
  'cost:get-metrics': void;
}

// ==================== System Integration Types ====================

export interface SystemInfo {
  cpuUsage: number;
  memoryUsage: number;
  gpuUsage?: number;
  processes: ProcessInfo[];
  uptime: number;
}

export interface ProcessInfo {
  pid: number;
  name: string;
  cpuUsage: number;
  memoryUsage: number;
}

export interface FileOperation {
  type: 'create' | 'read' | 'update' | 'delete' | 'move' | 'copy';
  source: string;
  destination?: string;
  content?: string;
}

export interface ApplicationLaunchOptions {
  name: string;
  args?: string[];
  cwd?: string;
  elevated?: boolean;
}
