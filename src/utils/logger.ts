import fs from 'fs';
import path from 'path';

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

const LOG_LEVELS: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

const COLORS: Record<LogLevel, string> = {
  debug: '\x1b[36m', // Cyan
  info: '\x1b[32m',  // Green
  warn: '\x1b[33m',  // Yellow
  error: '\x1b[31m', // Red
};

const RESET = '\x1b[0m';

class Logger {
  private minLevel: LogLevel;
  private logDir: string;
  private logFile: string;

  constructor() {
    this.minLevel = (process.env.LOG_LEVEL as LogLevel) || 'info';
    this.logDir = process.env.LOG_DIR || path.join(process.cwd(), 'data', 'logs');
    this.logFile = path.join(this.logDir, 'michael.log');
    this.ensureLogDir();
  }

  private ensureLogDir(): void {
    if (!fs.existsSync(this.logDir)) {
      fs.mkdirSync(this.logDir, { recursive: true });
    }
  }

  private shouldLog(level: LogLevel): boolean {
    return LOG_LEVELS[level] >= LOG_LEVELS[this.minLevel];
  }

  private rotateIfNeeded(): void {
    try {
      const stats = fs.statSync(this.logFile);
      if (stats.size > 10 * 1024 * 1024) { // 10MB
        const backupFile = this.logFile + '.1';
        // Remove old backup if exists
        if (fs.existsSync(backupFile)) {
          fs.unlinkSync(backupFile);
        }
        fs.renameSync(this.logFile, backupFile);
      }
    } catch {
      // File doesn't exist yet or other error - ignore
    }
  }

  private formatMessage(level: LogLevel, message: string): string {
    const timestamp = new Date().toISOString();
    return `[${timestamp}] [${level.toUpperCase()}] ${message}`;
  }

  log(level: LogLevel, message: string): void {
    if (!this.shouldLog(level)) return;

    const formattedMessage = this.formatMessage(level, message);

    // Console output with colors
    const coloredMessage = `${COLORS[level]}${formattedMessage}${RESET}`;
    console.log(coloredMessage);

    // File output (with rotation)
    try {
      this.rotateIfNeeded();
      fs.appendFileSync(this.logFile, formattedMessage + '\n');
    } catch (error) {
      console.error('Failed to write log to file:', error);
    }
  }

  debug(message: string): void {
    this.log('debug', message);
  }

  info(message: string): void {
    this.log('info', message);
  }

  warn(message: string): void {
    this.log('warn', message);
  }

  error(message: string): void {
    this.log('error', message);
  }
}

// Singleton instance
const logger = new Logger();

// Export log function
export function log(level: LogLevel, message: string): void {
  logger.log(level, message);
}

// Export convenience functions
export const debug = (message: string) => logger.debug(message);
export const info = (message: string) => logger.info(message);
export const warn = (message: string) => logger.warn(message);
export const error = (message: string) => logger.error(message);
