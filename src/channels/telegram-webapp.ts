/**
 * Telegram Web App Integration
 *
 * Handles communication between Telegram Mini App (Web App) and Gateway.
 * Manages session state for A2UI forms.
 *
 * @see https://core.telegram.org/bots/webapps
 */

import { log } from '../utils/logger.js';
import { SurfaceUpdate } from '../a2ui/types.js';
import { A2UISessionStore, InMemorySessionStore } from './telegram-renderer.js';

// --- Types ---

/**
 * Web App session data
 */
export interface WebAppSession {
  /** Session ID */
  sessionId: string;
  /** User ID (Telegram) */
  userId: string;
  /** Chat ID */
  chatId: number;
  /** A2UI Surface */
  surface: SurfaceUpdate;
  /** Data model state */
  dataModel: Record<string, unknown>;
  /** Creation timestamp */
  createdAt: number;
  /** Last updated timestamp */
  updatedAt: number;
}

/**
 * Web App message from client
 */
export interface WebAppClientMessage {
  type: 'init' | 'action' | 'update' | 'close';
  sessionId: string;
  /** Action data (for 'action' type) */
  action?: {
    name: string;
    context?: Record<string, unknown>;
  };
  /** Data model updates (for 'update' type) */
  data?: Record<string, unknown>;
}

/**
 * Web App message to client
 */
export interface WebAppServerMessage {
  type: 'surface' | 'data' | 'error' | 'close';
  /** Surface update (for 'surface' type) */
  surface?: SurfaceUpdate;
  /** Data model (for 'data' type) */
  data?: Record<string, unknown>;
  /** Error message (for 'error' type) */
  error?: string;
}

// --- Configuration ---

export interface TelegramWebAppConfig {
  /** Session store */
  sessionStore?: A2UISessionStore;
  /** Session TTL in milliseconds */
  sessionTtlMs?: number;
}

// --- Telegram Web App Manager ---

/**
 * Manages Telegram Web App sessions and communication
 *
 * @example
 * ```ts
 * const webAppManager = new TelegramWebAppManager();
 *
 * // Create session for Web App
 * const session = webAppManager.createSession('user_123', 12345, surface, dataModel);
 *
 * // Handle client message
 * const response = webAppManager.handleMessage({
 *   type: 'init',
 *   sessionId: session.sessionId,
 * });
 * ```
 */
export class TelegramWebAppManager {
  private sessions = new Map<string, WebAppSession>();
  private config: Required<TelegramWebAppConfig>;
  private cleanupInterval: NodeJS.Timeout | null = null;

  constructor(config: TelegramWebAppConfig = {}) {
    this.config = {
      sessionStore: config.sessionStore || new InMemorySessionStore(),
      sessionTtlMs: config.sessionTtlMs || 30 * 60 * 1000, // 30 minutes
    };

    // Cleanup expired sessions every 5 minutes
    this.cleanupInterval = setInterval(() => this.cleanup(), 5 * 60 * 1000);
  }

  /**
   * Create a new Web App session
   */
  createSession(
    userId: string,
    chatId: number,
    surface: SurfaceUpdate,
    dataModel: Record<string, unknown> = {}
  ): WebAppSession {
    const sessionId = this.generateSessionId();
    const now = Date.now();

    const session: WebAppSession = {
      sessionId,
      userId,
      chatId,
      surface,
      dataModel,
      createdAt: now,
      updatedAt: now,
    };

    this.sessions.set(sessionId, session);

    // Also store in the shared session store
    this.config.sessionStore.set(sessionId, surface, this.config.sessionTtlMs);

    log('debug', `📱 Created Web App session: ${sessionId}`);

    return session;
  }

  /**
   * Get session by ID
   */
  getSession(sessionId: string): WebAppSession | undefined {
    return this.sessions.get(sessionId);
  }

  /**
   * Update session data model
   */
  updateDataModel(sessionId: string, updates: Record<string, unknown>): boolean {
    const session = this.sessions.get(sessionId);
    if (!session) {
      return false;
    }

    session.dataModel = { ...session.dataModel, ...updates };
    session.updatedAt = Date.now();

    return true;
  }

  /**
   * Handle message from Web App client
   */
  handleMessage(message: WebAppClientMessage): WebAppServerMessage {
    const session = this.sessions.get(message.sessionId);

    switch (message.type) {
      case 'init':
        // Client requesting initial state
        if (!session) {
          return { type: 'error', error: 'Session not found' };
        }
        return {
          type: 'surface',
          surface: session.surface,
          data: session.dataModel,
        };

      case 'update':
        // Client updating data model
        if (!session) {
          return { type: 'error', error: 'Session not found' };
        }
        if (message.data) {
          this.updateDataModel(message.sessionId, message.data);
        }
        return { type: 'data', data: session.dataModel };

      case 'action':
        // Client triggering action - will be handled by Gateway
        log('debug', `📱 Web App action: ${message.action?.name}`);
        return { type: 'close' };

      case 'close':
        // Client closing Web App
        this.deleteSession(message.sessionId);
        return { type: 'close' };

      default:
        return { type: 'error', error: 'Unknown message type' };
    }
  }

  /**
   * Delete a session
   */
  deleteSession(sessionId: string): void {
    this.sessions.delete(sessionId);
    this.config.sessionStore.delete(sessionId);
    log('debug', `📱 Deleted Web App session: ${sessionId}`);
  }

  /**
   * Cleanup expired sessions
   */
  private cleanup(): void {
    const now = Date.now();
    const ttl = this.config.sessionTtlMs;

    for (const [id, session] of this.sessions) {
      if (now - session.updatedAt > ttl) {
        this.deleteSession(id);
      }
    }
  }

  /**
   * Generate unique session ID
   */
  private generateSessionId(): string {
    return `webapp_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }

  /**
   * Destroy manager and cleanup resources
   */
  destroy(): void {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
      this.cleanupInterval = null;
    }
    this.sessions.clear();
  }

  /**
   * Get all active sessions for a user
   */
  getSessionsByUser(userId: string): WebAppSession[] {
    return Array.from(this.sessions.values()).filter((s) => s.userId === userId);
  }
}

// --- Factory Function ---

/**
 * Create a TelegramWebAppManager instance
 */
export function createWebAppManager(config?: TelegramWebAppConfig): TelegramWebAppManager {
  return new TelegramWebAppManager(config);
}

// --- Telegram Web App SDK Helpers ---

/**
 * Generate Web App init data validation hash
 * Used to verify data from Telegram
 *
 * @see https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
 */
export function validateWebAppInitData(
  initData: string,
  botToken: string
): { valid: boolean; data?: Record<string, string> } {
  try {
    const crypto = require('crypto');

    // Parse init data
    const params = new URLSearchParams(initData);
    const hash = params.get('hash');
    params.delete('hash');

    // Sort and join
    const dataCheckString = Array.from(params.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, value]) => `${key}=${value}`)
      .join('\n');

    // Generate secret key
    const secretKey = crypto
      .createHmac('sha256', 'WebAppData')
      .update(botToken)
      .digest();

    // Generate hash
    const calculatedHash = crypto
      .createHmac('sha256', secretKey)
      .update(dataCheckString)
      .digest('hex');

    if (calculatedHash !== hash) {
      return { valid: false };
    }

    // Parse data
    const data: Record<string, string> = {};
    for (const [key, value] of params) {
      data[key] = value;
    }

    return { valid: true, data };
  } catch (error) {
    log('error', `Failed to validate Web App init data: ${error}`);
    return { valid: false };
  }
}

/**
 * Parse Telegram user from init data
 */
export function parseWebAppUser(initData: string): {
  id: number;
  firstName: string;
  lastName?: string;
  username?: string;
  languageCode?: string;
} | null {
  try {
    const params = new URLSearchParams(initData);
    const userJson = params.get('user');
    if (!userJson) return null;

    const user = JSON.parse(userJson);
    return {
      id: user.id,
      firstName: user.first_name,
      lastName: user.last_name,
      username: user.username,
      languageCode: user.language_code,
    };
  } catch {
    return null;
  }
}
