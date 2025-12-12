"use strict";
/**
 * JARVIS Voice Agent - Logger Utility
 */
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.logger = exports.LogLevel = void 0;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
var LogLevel;
(function (LogLevel) {
    LogLevel[LogLevel["DEBUG"] = 0] = "DEBUG";
    LogLevel[LogLevel["INFO"] = 1] = "INFO";
    LogLevel[LogLevel["WARN"] = 2] = "WARN";
    LogLevel[LogLevel["ERROR"] = 3] = "ERROR";
})(LogLevel || (exports.LogLevel = LogLevel = {}));
class Logger {
    constructor() {
        this.logLevel = LogLevel.INFO;
        this.logStream = null;
        const logsDir = path_1.default.join(process.cwd(), 'logs');
        if (!fs_1.default.existsSync(logsDir)) {
            fs_1.default.mkdirSync(logsDir, { recursive: true });
        }
        const timestamp = new Date().toISOString().split('T')[0];
        this.logFile = path_1.default.join(logsDir, `jarvis-${timestamp}.log`);
        this.logStream = fs_1.default.createWriteStream(this.logFile, { flags: 'a' });
    }
    setLevel(level) {
        this.logLevel = level;
    }
    formatMessage(level, message, meta) {
        const timestamp = new Date().toISOString();
        const metaStr = meta ? ` | ${JSON.stringify(meta)}` : '';
        return `[${timestamp}] [${level}] ${message}${metaStr}`;
    }
    write(level, levelName, message, meta) {
        if (level < this.logLevel)
            return;
        const formatted = this.formatMessage(levelName, message, meta);
        // Console output
        console.log(formatted);
        // File output
        if (this.logStream) {
            this.logStream.write(formatted + '\n');
        }
    }
    debug(message, meta) {
        this.write(LogLevel.DEBUG, 'DEBUG', message, meta);
    }
    info(message, meta) {
        this.write(LogLevel.INFO, 'INFO', message, meta);
    }
    warn(message, meta) {
        this.write(LogLevel.WARN, 'WARN', message, meta);
    }
    error(message, meta) {
        this.write(LogLevel.ERROR, 'ERROR', message, meta);
    }
    close() {
        if (this.logStream) {
            this.logStream.end();
            this.logStream = null;
        }
    }
}
exports.logger = new Logger();
