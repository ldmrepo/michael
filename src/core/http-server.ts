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
import { ClaudeCodeAgent, A2UIAgentMessage } from '../agent/claude-code.js';
import {
  generateRunId,
  generateThreadId,
  generateMessageId,
  generateToolCallId,
  createRunStarted,
  createRunFinished,
  createRunError,
  createTextMessageStart,
  createTextMessageContent,
  createTextMessageEnd,
  createToolCallStart,
  createToolCallEnd,
  createToolCallResult,
  AGUIEvent,
} from './events.js';
import { formatSSEEvent, SSE_HEADERS, SSE_DONE } from './sse.js';

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
  /** Path to frontend (Next.js) build */
  frontendPath?: string;
}

// A2UI MIME type
const A2UI_MIME_TYPE = 'application/json+a2ui';
const A2UI_TOOL_NAME = 'render_a2ui';

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
  private agent: ClaudeCodeAgent | null = null;

  constructor(config: HttpServerConfig = {}) {
    this.config = {
      port: config.port || 3000,
      host: config.host || '0.0.0.0',
      webappPath: config.webappPath || path.join(process.cwd(), 'dist/webapp'),
      baseUrl: config.baseUrl || `http://localhost:${config.port || 3000}`,
      frontendPath: config.frontendPath || path.join(process.cwd(), 'frontend/.next'),
    };

    this.app = express();
    this.webAppManager = new TelegramWebAppManager();
    this.setupRoutes();
  }

  /**
   * Set the Claude Code Agent for chat streaming
   */
  setAgent(agent: ClaudeCodeAgent): void {
    this.agent = agent;
    log('info', '🤖 Agent connected to HTTP Server');
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

    // API: Chat Stream (AG-UI SSE)
    this.app.post('/api/chat/stream', async (req: Request, res: Response) => {
      await this.handleChatStream(req, res);
    });

    // API: Chat (non-streaming, JSON response)
    this.app.post('/api/chat', async (req: Request, res: Response) => {
      await this.handleChat(req, res);
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

  /**
   * Handle SSE chat stream request (AG-UI protocol)
   */
  private async handleChatStream(req: Request, res: Response): Promise<void> {
    const { message, userId = 'web_user', threadId: reqThreadId } = req.body;

    if (!message) {
      res.status(400).json({ error: 'Message is required' });
      return;
    }

    if (!this.agent) {
      res.status(503).json({ error: 'Agent not available' });
      return;
    }

    // Set SSE headers
    res.setHeader('Content-Type', SSE_HEADERS['Content-Type']);
    res.setHeader('Cache-Control', SSE_HEADERS['Cache-Control']);
    res.setHeader('Connection', SSE_HEADERS.Connection);
    res.setHeader('X-Accel-Buffering', 'no');

    const threadId = reqThreadId || generateThreadId();
    const runId = generateRunId();
    const messageId = generateMessageId();

    // Helper to send SSE event
    const sendEvent = (event: AGUIEvent) => {
      res.write(formatSSEEvent(event));
    };

    try {
      // 1. RUN_STARTED
      sendEvent(createRunStarted(threadId, runId));

      // 2. TEXT_MESSAGE_START
      sendEvent(createTextMessageStart(threadId, runId, messageId, 'assistant'));

      let fullText = '';
      const a2uiMessages: A2UIAgentMessage[] = [];

      // 3. Stream response from Agent
      await this.agent.chatWithStreaming(
        userId,
        message,
        {
          onTextContent: (delta: string, _snapshot: string) => {
            fullText += delta;
            sendEvent(createTextMessageContent(threadId, runId, messageId, delta));
          },
          onA2UI: (messages: A2UIAgentMessage[]) => {
            a2uiMessages.push(...messages);
          },
          onError: (error: Error) => {
            log('error', `Chat stream error: ${error.message}`);
          },
        }
      );

      // 4. TEXT_MESSAGE_END
      sendEvent(createTextMessageEnd(threadId, runId, messageId));

      // 5. A2UI messages (if any) - wrapped in TOOL_CALL events
      if (a2uiMessages.length > 0) {
        const toolCallId = generateToolCallId();

        // TOOL_CALL_START
        sendEvent(createToolCallStart(threadId, runId, toolCallId, A2UI_TOOL_NAME));

        // TOOL_CALL_RESULT for each A2UI message
        for (const a2uiMsg of a2uiMessages) {
          sendEvent(createToolCallResult(threadId, runId, toolCallId, a2uiMsg, A2UI_MIME_TYPE));
        }

        // TOOL_CALL_END
        sendEvent(createToolCallEnd(threadId, runId, toolCallId));
      }

      // 6. RUN_FINISHED
      sendEvent(createRunFinished(threadId, runId));

      // End SSE stream
      res.write(SSE_DONE);
      res.end();

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      log('error', `Chat stream failed: ${errorMessage}`);

      // Send error event
      sendEvent(createRunError(threadId, runId, errorMessage, 'CHAT_ERROR'));
      res.write(SSE_DONE);
      res.end();
    }
  }

  /**
   * Handle non-streaming chat request (JSON response)
   */
  private async handleChat(req: Request, res: Response): Promise<void> {
    const { message, userId = 'web_user' } = req.body;

    if (!message) {
      res.status(400).json({ error: 'Message is required' });
      return;
    }

    if (!this.agent) {
      res.status(503).json({ error: 'Agent not available' });
      return;
    }

    try {
      const response = await this.agent.chat(userId, message);
      res.json({
        success: true,
        response,
        userId,
        timestamp: new Date().toISOString(),
      });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      log('error', `Chat failed: ${errorMessage}`);
      res.status(500).json({ error: errorMessage });
    }
  }
}

/**
 * Create an HttpServer instance
 */
export function createHttpServer(config?: HttpServerConfig): HttpServer {
  return new HttpServer(config);
}
