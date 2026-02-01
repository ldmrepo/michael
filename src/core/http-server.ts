/**
 * HTTP Server for Michael
 *
 * Provides HTTP endpoints for:
 * - Static files (Mini App)
 * - Web App session API
 * - A2A Agent Card
 * - Health check
 */

import express, { Express, Request, Response } from 'express';
import path from 'path';
import { Server } from 'http';
import { TelegramWebAppManager } from '../channels/telegram-webapp.js';
import { getMichaelAgentCard } from '../a2a/agent-card.js';
import { log } from '../utils/logger.js';

// --- Types ---

export interface HttpServerConfig {
  /** HTTP server port */
  port?: number;
  /** Host to bind to */
  host?: string;
  /** Path to static webapp files */
  webappPath?: string;
  /** Base URL for agent card */
  baseUrl?: string;
}

// --- HTTP Server ---

/**
 * HTTP Server for Michael
 *
 * @example
 * ```ts
 * const httpServer = new HttpServer({ port: 3000 });
 * await httpServer.start();
 *
 * // Get WebAppManager for Telegram integration
 * const webAppManager = httpServer.getWebAppManager();
 * ```
 */
export class HttpServer {
  private app: Express;
  private server: Server | null = null;
  private webAppManager: TelegramWebAppManager;
  private config: Required<HttpServerConfig>;

  constructor(config: HttpServerConfig = {}) {
    this.config = {
      port: config.port || 3000,
      host: config.host || '0.0.0.0',
      webappPath: config.webappPath || path.join(process.cwd(), 'dist/webapp'),
      baseUrl: config.baseUrl || `http://localhost:${config.port || 3000}`,
    };

    this.app = express();
    this.webAppManager = new TelegramWebAppManager();
    this.setupRoutes();
  }

  /**
   * Setup Express routes
   */
  private setupRoutes(): void {
    // JSON parsing
    this.app.use(express.json());

    // CORS for development
    this.app.use((_req, res, next) => {
      res.header('Access-Control-Allow-Origin', '*');
      res.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
      res.header('Access-Control-Allow-Headers', 'Content-Type, Authorization');
      if (_req.method === 'OPTIONS') {
        res.sendStatus(200);
        return;
      }
      next();
    });

    // Health check
    this.app.get('/health', (_req: Request, res: Response) => {
      res.json({
        status: 'ok',
        timestamp: new Date().toISOString(),
        uptime: process.uptime(),
      });
    });

    // A2A Agent Card
    this.app.get('/.well-known/agent.json', (_req: Request, res: Response) => {
      res.json(getMichaelAgentCard(this.config.baseUrl));
    });

    // API: Get session
    this.app.get('/api/webapp/session/:id', (req: Request, res: Response) => {
      const sessionId = req.params.id as string;
      const session = this.webAppManager.getSession(sessionId);
      if (!session) {
        res.status(404).json({ error: 'Session not found' });
        return;
      }
      res.json({
        sessionId: session.sessionId,
        surface: session.surface,
        dataModel: session.dataModel,
      });
    });

    // API: Update session
    this.app.post('/api/webapp/session/:id', (req: Request, res: Response) => {
      const sessionId = req.params.id as string;
      const success = this.webAppManager.updateDataModel(
        sessionId,
        req.body.data || {}
      );
      if (!success) {
        res.status(404).json({ error: 'Session not found' });
        return;
      }
      const session = this.webAppManager.getSession(sessionId);
      res.json({ dataModel: session?.dataModel });
    });

    // API: Handle client message
    this.app.post('/api/webapp/message', (req: Request, res: Response) => {
      const response = this.webAppManager.handleMessage(req.body);
      res.json(response);
    });

    // Static files for Mini App
    this.app.use('/webapp', express.static(this.config.webappPath));

    // SPA fallback - serve index.html for client-side routing
    // Express 5 uses named catch-all: {*path} instead of *
    this.app.get('/webapp/{*path}', (_req: Request, res: Response) => {
      const indexPath = path.join(this.config.webappPath, 'index.html');
      res.sendFile(indexPath, (err) => {
        if (err) {
          res.status(404).json({ error: 'Mini App not found' });
        }
      });
    });
  }

  /**
   * Start the HTTP server
   */
  async start(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.server = this.app.listen(this.config.port, this.config.host, () => {
          log('info', `🌐 HTTP Server started on http://${this.config.host}:${this.config.port}`);
          log('info', `   Mini App: http://${this.config.host}:${this.config.port}/webapp/`);
          log('info', `   Health: http://${this.config.host}:${this.config.port}/health`);
          resolve();
        });

        this.server.on('error', (err) => {
          log('error', `❌ HTTP Server error: ${err}`);
          reject(err);
        });
      } catch (err) {
        reject(err);
      }
    });
  }

  /**
   * Stop the HTTP server
   */
  async stop(): Promise<void> {
    return new Promise((resolve) => {
      if (this.server) {
        this.webAppManager.destroy();
        this.server.close(() => {
          log('info', '🌐 HTTP Server stopped');
          this.server = null;
          resolve();
        });
      } else {
        resolve();
      }
    });
  }

  /**
   * Get the WebAppManager instance
   */
  getWebAppManager(): TelegramWebAppManager {
    return this.webAppManager;
  }

  /**
   * Get the Express app (for testing)
   */
  getApp(): Express {
    return this.app;
  }

  /**
   * Get the server port
   */
  getPort(): number {
    return this.config.port;
  }
}

/**
 * Create an HttpServer instance
 */
export function createHttpServer(config?: HttpServerConfig): HttpServer {
  return new HttpServer(config);
}
