/**
 * JARVIS Voice Agent - Logger Utility
 */

import fs from 'fs';
import path from 'path';

export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
}

class Logger {
  private logLevel: LogLevel = LogLevel.INFO;
  private logFile: string;
  private logStream: fs.WriteStream | null = null;

  constructor() {
    const logsDir = path.join(process.cwd(), 'logs');
    if (!fs.existsSync(logsDir)) {
      fs.mkdirSync(logsDir, { recursive: true });
    }

    const timestamp = new Date().toISOString().split('T')[0];
    this.logFile = path.join(logsDir, `jarvis-${timestamp}.log`);

    this.logStream = fs.createWriteStream(this.logFile, { flags: 'a' });
  }

  setLevel(level: LogLevel) {
    this.logLevel = level;
  }

  private formatMessage(level: string, message: string, meta?: any): string {
    const timestamp = new Date().toISOString();
    const metaStr = meta ? ` | ${JSON.stringify(meta)}` : '';
    return `[${timestamp}] [${level}] ${message}${metaStr}`;
  }

  private write(level: LogLevel, levelName: string, message: string, meta?: any) {
    if (level < this.logLevel) return;

    const formatted = this.formatMessage(levelName, message, meta);

    // Console output
    console.log(formatted);

    // File output
    if (this.logStream) {
      this.logStream.write(formatted + '\n');
    }
  }

  debug(message: string, meta?: any) {
    this.write(LogLevel.DEBUG, 'DEBUG', message, meta);
  }

  info(message: string, meta?: any) {
    this.write(LogLevel.INFO, 'INFO', message, meta);
  }

  warn(message: string, meta?: any) {
    this.write(LogLevel.WARN, 'WARN', message, meta);
  }

  error(message: string, meta?: any) {
    this.write(LogLevel.ERROR, 'ERROR', message, meta);
  }

  close() {
    if (this.logStream) {
      this.logStream.end();
      this.logStream = null;
    }
  }
}

export const logger = new Logger();
