/**
 * Finance Agent Server
 *
 * A2A-compliant server for the Finance Agent.
 * Handles JSON-RPC requests and serves the AgentCard.
 */
import express, { Request, Response } from 'express';
import { A2AServer } from '../../a2a/server.js';
import { extractTextFromMessage } from '../../a2a/types.js';
import { createFinanceAgentCard } from './agent.js';
import { FinanceAgentExecutor } from './executor.js';
import { log } from '../../utils/logger.js';

/** Default port for Finance Agent */
const DEFAULT_PORT = 8001;

/** Default host */
const DEFAULT_HOST = '127.0.0.1';

/**
 * Finance Agent Server configuration
 */
export interface FinanceServerConfig {
  /** Port to listen on */
  port?: number;
  /** Host to bind to */
  host?: string;
  /** Base URL for external access (for AgentCard) */
  baseUrl?: string;
}

/**
 * Finance Agent Server
 *
 * Standalone A2A server for the Finance Agent.
 */
export class FinanceAgentServer {
  private app: express.Express;
  private server: ReturnType<express.Express['listen']> | null = null;
  private a2aServer: A2AServer;
  private executor: FinanceAgentExecutor;
  private config: Required<FinanceServerConfig>;

  constructor(config: FinanceServerConfig = {}) {
    const port = config.port ?? parseInt(process.env.FINANCE_AGENT_PORT || String(DEFAULT_PORT), 10);
    const host = config.host ?? process.env.FINANCE_AGENT_HOST ?? DEFAULT_HOST;

    this.config = {
      port,
      host,
      baseUrl: config.baseUrl ?? `http://${host}:${port}`,
    };

    this.app = express();
    this.executor = new FinanceAgentExecutor();
    this.a2aServer = new A2AServer({ baseUrl: this.config.baseUrl });

    this.setupA2AHandler();
    this.setupRoutes();
  }

  /**
   * Setup A2A message handler
   */
  private setupA2AHandler(): void {
    this.a2aServer.setHandler({
      processMessage: async (message, metadata) => {
        const context = {
          taskId: `task_${Date.now()}`,
          message,
          metadata,
        };

        log('debug', `💰 Finance Agent processing: ${extractTextFromMessage(message).substring(0, 50)}...`);

        return this.executor.execute(context);
      },
    });
  }

  /**
   * Setup Express routes
   */
  private setupRoutes(): void {
    this.app.use(express.json());

    // CORS
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
        agent: 'finance',
        timestamp: new Date().toISOString(),
      });
    });

    // Agent Card endpoint (A2A standard)
    this.app.get('/.well-known/agent.json', (_req: Request, res: Response) => {
      res.json(createFinanceAgentCard(this.config.baseUrl));
    });

    // A2A JSON-RPC endpoint
    this.app.post('/', async (req: Request, res: Response) => {
      try {
        const response = await this.a2aServer.handleRequest(req.body);
        res.json(response);
      } catch (error) {
        log('error', `Finance Agent error: ${error}`);
        res.status(500).json({
          jsonrpc: '2.0',
          id: req.body?.id,
          error: {
            code: -32603,
            message: error instanceof Error ? error.message : 'Internal error',
          },
        });
      }
    });
  }

  /**
   * Start the server
   */
  async start(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.server = this.app.listen(this.config.port, this.config.host, () => {
          log('info', `💰 Finance Agent running at ${this.config.baseUrl}`);
          log('info', `📋 Agent Card: ${this.config.baseUrl}/.well-known/agent.json`);
          log('info', `❤️  Health: ${this.config.baseUrl}/health`);
          resolve();
        });

        this.server.on('error', (err) => {
          log('error', `❌ Finance Agent error: ${err}`);
          reject(err);
        });
      } catch (err) {
        reject(err);
      }
    });
  }

  /**
   * Stop the server
   */
  async stop(): Promise<void> {
    return new Promise((resolve) => {
      if (this.server) {
        this.a2aServer.destroy();
        this.server.close(() => {
          log('info', '💰 Finance Agent stopped');
          this.server = null;
          resolve();
        });
      } else {
        resolve();
      }
    });
  }

  /**
   * Get the Express app (for testing)
   */
  getApp(): express.Express {
    return this.app;
  }

  /**
   * Get server configuration
   */
  getConfig(): Required<FinanceServerConfig> {
    return this.config;
  }
}

/**
 * Start Finance Agent server
 */
export async function startFinanceAgentServer(
  config?: FinanceServerConfig
): Promise<FinanceAgentServer> {
  const server = new FinanceAgentServer(config);
  await server.start();
  return server;
}

// Entry point for direct execution
const isMainModule = import.meta.url === `file://${process.argv[1]}`;

if (isMainModule) {
  startFinanceAgentServer().catch((error) => {
    console.error('Failed to start Finance Agent:', error);
    process.exit(1);
  });
}
