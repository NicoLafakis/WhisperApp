"use strict";
/**
 * JARVIS Voice Agent - Configuration Manager
 */
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.configManager = exports.ConfigManager = void 0;
const dotenv = __importStar(require("dotenv"));
dotenv.config();
class ConfigManager {
    constructor() {
        this.config = this.loadConfig();
    }
    loadConfig() {
        return {
            openai: {
                apiKey: process.env.OPENAI_API_KEY || '',
            },
            elevenlabs: {
                apiKey: process.env.ELEVENLABS_API_KEY || '',
                voiceId: process.env.ELEVENLABS_VOICE_ID || 'EXAVITQu4MsJ5X4xQvF9',
            },
            audio: {
                sampleRate: parseInt(process.env.SAMPLE_RATE || '16000'),
                channels: parseInt(process.env.AUDIO_CHANNELS || '1'),
                bitDepth: 16,
            },
            wakeWord: {
                keyword: process.env.WAKE_WORD || 'jarvis',
                sensitivity: parseFloat(process.env.WAKE_WORD_SENSITIVITY || '0.5'),
            },
            routing: {
                defaultMode: process.env.DEFAULT_MODE || 'premium',
                dailyBudget: parseFloat(process.env.DAILY_BUDGET_USD || '1.00'),
                monthlyBudget: parseFloat(process.env.MONTHLY_BUDGET_USD || '30.00'),
                peakHoursStart: parseInt(process.env.PEAK_HOURS_START || '9'),
                peakHoursEnd: parseInt(process.env.PEAK_HOURS_END || '17'),
            },
            voice: {
                name: 'alloy',
                speed: 1.0,
            },
            security: {
                requireConfirmation: [
                    'delete_file',
                    'modify_system_settings',
                    'uninstall_application',
                    'modify_registry',
                ],
                blocked: [
                    'access_credentials',
                    'modify_admin_protected',
                    'run_arbitrary_powershell',
                ],
            },
        };
    }
    getConfig() {
        return { ...this.config };
    }
    updateConfig(updates) {
        this.config = {
            ...this.config,
            ...updates,
        };
    }
    get openaiApiKey() {
        return this.config.openai.apiKey;
    }
    get audioConfig() {
        return this.config.audio;
    }
    get routingConfig() {
        return this.config.routing;
    }
}
exports.ConfigManager = ConfigManager;
exports.configManager = new ConfigManager();
