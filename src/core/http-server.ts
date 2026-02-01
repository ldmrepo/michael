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
import { A2AOrchestrator } from '../a2a/orchestrator.js';
import { log } from '../utils/logger.js';
import { ClaudeCodeAgent, A2UIAgentMessage } from '../agent/claude-code.js';
import {
  generateRunId,
  generateThreadId,
  generateMessageId,
  createRunStarted,
  createRunFinished,
  createRunError,
  createTextMessageStart,
  createTextMessageContent,
  createTextMessageEnd,
  AGUIEvent,
} from './events.js';
import { formatSSEEvent, SSE_HEADERS, SSE_DONE } from './sse.js';
import {
  wrapA2UIMessages,
  createTextA2UIMessages,
  A2UIMessagePayload,
  convertLegacyToStandard,
  LegacyA2UIMessage,
} from './a2ui.js';

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
  private orchestrator: A2AOrchestrator;

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
    this.orchestrator = new A2AOrchestrator();

    // Register Finance Agent (auto-register if URL is set)
    const financeAgentUrl = process.env.FINANCE_AGENT_URL || 'http://127.0.0.1:8001';
    this.orchestrator.registerAgent('finance', financeAgentUrl);

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

    // API: Finance Agent delegation via Orchestrator
    this.app.post('/api/finance/chat', async (req: Request, res: Response) => {
      await this.handleFinanceChat(req, res);
    });

    // API: List registered agents
    this.app.get('/api/agents', (_req: Request, res: Response) => {
      const agents = this.orchestrator.getAllAgents().map((agent) => ({
        name: agent.name,
        url: agent.url,
        healthy: agent.healthy,
        lastHealthCheck: agent.lastHealthCheck,
        skills: agent.card?.skills?.map((s) => s.id) || [],
      }));
      res.json({ agents });
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

      // 5. A2UI messages - ALWAYS generate A2UI for proper rendering
      // If agent provided A2UI messages, use them; otherwise convert text to A2UI
      let finalA2UIMessages: A2UIMessagePayload[];

      if (a2uiMessages.length > 0) {
        // Agent provides legacy format messages, convert to v0.8 standard
        finalA2UIMessages = a2uiMessages
          .map((msg) => convertLegacyToStandard(msg as unknown as LegacyA2UIMessage))
          .filter((msg): msg is A2UIMessagePayload => msg !== null);
      } else if (fullText.trim()) {
        // Convert plain text to A2UI Text component (AG-UI + A2UI standard)
        finalA2UIMessages = createTextA2UIMessages(fullText.trim());
      } else {
        finalA2UIMessages = [];
      }

      // Wrap A2UI messages in TOOL_CALL events
      if (finalA2UIMessages.length > 0) {
        const toolEvents = wrapA2UIMessages(finalA2UIMessages, threadId, runId);
        for (const event of toolEvents) {
          sendEvent(event);
        }
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

  /**
   * Handle Finance Agent chat request (delegated via Orchestrator)
   */
  private async handleFinanceChat(req: Request, res: Response): Promise<void> {
    const { message, threadId } = req.body;

    if (!message) {
      res.status(400).json({ error: 'Message is required' });
      return;
    }

    try {
      // Check if Finance Agent is healthy
      const financeAgent = this.orchestrator.getAgent('finance');
      if (!financeAgent) {
        res.status(503).json({ error: 'Finance Agent not registered' });
        return;
      }

      if (!financeAgent.healthy) {
        // Try to discover/health check the agent
        await this.orchestrator.discoverAgent('finance');
        const updatedAgent = this.orchestrator.getAgent('finance');
        if (!updatedAgent?.healthy) {
          res.status(503).json({ error: 'Finance Agent is not available' });
          return;
        }
      }

      log('debug', `💰 Delegating to Finance Agent: ${message.substring(0, 50)}...`);

      // Send message to Finance Agent via Orchestrator
      const response = await this.orchestrator.sendToAgent('finance', message, {
        threadId,
        source: 'michael-http-server',
      });

      res.json({
        success: true,
        response,
        agent: 'finance',
        timestamp: new Date().toISOString(),
      });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      log('error', `Finance chat failed: ${errorMessage}`);
      res.status(500).json({ error: errorMessage });
    }
  }

  /**
   * Get the Orchestrator instance
   */
  getOrchestrator(): A2AOrchestrator {
    return this.orchestrator;
  }
}

/**
 * Create an HttpServer instance
 */
export function createHttpServer(config?: HttpServerConfig): HttpServer {
  return new HttpServer(config);
}
