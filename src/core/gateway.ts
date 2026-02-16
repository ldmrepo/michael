import { WebSocketServer, WebSocket } from 'ws';
import { log } from '../utils/logger.js';
import { ClaudeCodeAgent } from '../agent/claude-code.js';
import {
  AGUIEventType,
  AGUIEvent,
  generateRunId,
  generateMessageId,
  createRunStarted,
  createRunFinished,
  createRunError,
  createTextMessageStart,
  createTextMessageContent,
  createTextMessageEnd,
  createToolCallStart,
  createToolCallEnd,
} from './events.js';

/**
 * Gateway 메시지 타입
 * AG-UI 프로토콜 호환 확장 (하위 호환성 유지)
 */
export interface GatewayMessage {
  from: 'telegram' | 'scheduler' | 'cli' | 'agent' | 'sentinel';
  to: 'agent' | 'telegram' | 'scheduler' | 'cli' | 'investment' | 'sentinel' | string;
  userId: string;
  content: string;
  metadata?: Record<string, any>;
  // AG-UI 확장 필드 (선택적)
  eventType?: AGUIEventType;
  threadId?: string;
  runId?: string;
  messageId?: string;
  // AG-UI 이벤트 특정 필드
  delta?: string;
  toolCallId?: string;
  toolCallName?: string;
  errorMessage?: string;
  errorCode?: string;
}

/**
 * 클라이언트 정보
 */
interface Client {
  id: string;
  ws: WebSocket;
  type: 'telegram' | 'scheduler' | 'cli' | 'agent' | 'sentinel' | 'unknown';
  connectedAt: number;
}

/**
 * Gateway 클래스
 * WebSocket 기반 중앙 메시지 허브
 */
export class Gateway {
  private wss: WebSocketServer | null = null;
  private clients: Map<string, Client> = new Map();
  private port: number;
  private host: string;
  private agent: ClaudeCodeAgent | null = null;
  private messageHandlers: Map<string, (message: GatewayMessage) => Promise<void>> = new Map();

  constructor(port: number = 18789, host: string = '127.0.0.1') {
    this.port = port;
    this.host = host;
  }

  /**
   * Agent 설정
   */
  setAgent(agent: ClaudeCodeAgent): void {
    this.agent = agent;
    log('info', '🤖 Agent connected to Gateway');
  }

  /**
   * Register a message handler for a specific target type
   * Messages with `to` matching the type will be routed to this handler
   */
  registerHandler(type: string, handler: (message: GatewayMessage) => Promise<void>): void {
    this.messageHandlers.set(type, handler);
    log('info', `📌 Handler registered for: ${type}`);
  }

  /**
   * Gateway 서버 시작
   */
  async start(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.wss = new WebSocketServer({
          port: this.port,
          host: this.host,
        });

        this.wss.on('listening', () => {
          log('info', `🚀 Gateway started on ${this.host}:${this.port}`);
          resolve();
        });

        this.wss.on('error', (error) => {
          log('error', `❌ Gateway error: ${error.message}`);
          reject(error);
        });

        this.wss.on('connection', (ws) => {
          this.handleConnection(ws);
        });

      } catch (error) {
        log('error', `❌ Failed to start Gateway: ${error}`);
        reject(error);
      }
    });
  }

  /**
   * 새로운 클라이언트 연결 처리
   */
  private handleConnection(ws: WebSocket): void {
    const clientId = this.generateClientId();
    
    log('info', `🔌 Client connected: ${clientId}`);

    // 초기 클라이언트 정보 (type은 첫 메시지에서 설정됨)
    const client: Client = {
      id: clientId,
      ws,
      type: 'cli', // 기본값
      connectedAt: Date.now(),
    };

    this.clients.set(clientId, client);

    // 메시지 수신 핸들러
    ws.on('message', (data) => {
      this.handleMessage(clientId, data);
    });

    // 연결 종료 핸들러
    ws.on('close', () => {
      log('info', `👋 Client disconnected: ${clientId}`);
      this.clients.delete(clientId);
    });

    // 에러 핸들러
    ws.on('error', (error) => {
      log('error', `❌ Client error (${clientId}): ${error.message}`);
    });

    // 연결 성공 응답
    this.send(clientId, {
      from: 'agent',
      to: 'cli',
      userId: 'system',
      content: 'Connected to Michael Gateway',
      metadata: { clientId },
    });
  }

  /**
   * 클라이언트로부터 메시지 수신
   */
  private async handleMessage(clientId: string, data: any): Promise<void> {
    const dataString = Buffer.isBuffer(data) ? data.toString() : String(data);
    try {
      const message: GatewayMessage = JSON.parse(dataString);
      
      log('debug', `📥 Message from ${clientId}: ${message.from} -> ${message.to}`);

      // 클라이언트 타입 업데이트
      const client = this.clients.get(clientId);
      if (client && message.from) {
        client.type = message.from;
      }

      // 메시지 라우팅
      await this.route(clientId, message);

    } catch (error) {
      log('error', `❌ Failed to parse message from ${clientId}: ${error}`);
      this.send(clientId, {
        from: 'agent',
        to: 'cli',
        userId: 'system',
        content: 'Invalid message format',
        metadata: { error: String(error) },
      });
    }
  }

  /**
   * 메시지 라우팅
   */
  private async route(senderId: string, message: GatewayMessage): Promise<void> {
    // Agent로 가는 메시지는 직접 처리
    if (message.to === 'agent') {
      await this.handleAgentMessage(senderId, message);
      return;
    }

    // 등록된 핸들러가 있으면 위임
    const handler = this.messageHandlers.get(message.to);
    if (handler) {
      try {
        await handler(message);
      } catch (error) {
        log('error', `❌ Handler error for ${message.to}: ${error}`);
      }
      return;
    }

    // 목적지 클라이언트 찾기
    const targetClient = this.findClientByType(message.to);

    if (targetClient) {
      // 특정 클라이언트로 전송
      this.send(targetClient.id, message);
    } else {
      // 목적지 클라이언트를 찾을 수 없음
      log('warn', `⚠️ No client found for type: ${message.to}`);
      
      // 송신자에게 에러 응답
      this.send(senderId, {
        from: 'agent',
        to: message.from,
        userId: message.userId,
        content: `No client available for: ${message.to}`,
        metadata: { error: 'CLIENT_NOT_FOUND' },
      });
    }
  }

  /**
   * Agent 메시지 처리 (레거시 동기식)
   */
  private async handleAgentMessage(
    senderId: string,
    message: GatewayMessage
  ): Promise<void> {
    if (!this.agent) {
      log('warn', '⚠️ Agent not available');
      this.send(senderId, {
        from: 'agent',
        to: message.from,
        userId: message.userId,
        content: 'Agent not available',
        metadata: { error: 'AGENT_NOT_AVAILABLE' },
      });
      return;
    }

    // 스트리밍 모드 사용 시 새 핸들러로 위임
    await this.handleAgentMessageWithStreaming(senderId, message);
  }

  /**
   * AG-UI 스트리밍을 지원하는 Agent 메시지 처리
   *
   * 이벤트 시퀀스: RUN_STARTED → TEXT_MESSAGE_START → TEXT_MESSAGE_CONTENT* → TEXT_MESSAGE_END → RUN_FINISHED
   * 에러 시: RUN_ERROR
   */
  private async handleAgentMessageWithStreaming(
    senderId: string,
    message: GatewayMessage
  ): Promise<void> {
    if (!this.agent) {
      return;
    }

    // userId를 threadId로 사용 (사용자별 대화 스레드)
    const threadId = message.threadId || `thread_${message.userId}`;
    const runId = generateRunId();
    const messageId = generateMessageId();

    // AG-UI 이벤트를 GatewayMessage로 변환하여 전송
    const sendAGUIEvent = (event: AGUIEvent, content: string = '') => {
      this.send(senderId, {
        from: 'agent',
        to: message.from,
        userId: message.userId,
        content,
        metadata: message.metadata,
        eventType: event.type,
        threadId: event.threadId,
        runId: event.runId,
        messageId: 'messageId' in event ? (event as any).messageId : undefined,
        delta: 'delta' in event ? (event as any).delta : undefined,
        toolCallId: 'toolCallId' in event ? (event as any).toolCallId : undefined,
        toolCallName: 'toolCallName' in event ? (event as any).toolCallName : undefined,
        errorMessage: 'message' in event && event.type === 'RUN_ERROR' ? (event as any).message : undefined,
        errorCode: 'code' in event ? (event as any).code : undefined,
      });
    };

    try {
      log('debug', `🤖 Processing with Agent (streaming): ${message.content.substring(0, 50)}...`);

      // RUN_STARTED 이벤트 전송
      sendAGUIEvent(createRunStarted(threadId, runId));

      // TEXT_MESSAGE_START 이벤트 전송
      sendAGUIEvent(createTextMessageStart(threadId, runId, messageId, 'assistant'));

      // Agent 호출 (스트리밍 콜백과 함께)
      const response = await this.agent.chatWithStreaming(
        message.userId,
        message.content,
        {
          onTextContent: (delta: string, _snapshot: string) => {
            sendAGUIEvent(createTextMessageContent(threadId, runId, messageId, delta));
          },
          onToolStart: (toolId: string, toolName: string) => {
            sendAGUIEvent(createToolCallStart(threadId, runId, toolId, toolName));
          },
          onToolEnd: (toolId: string, _result: unknown) => {
            sendAGUIEvent(createToolCallEnd(threadId, runId, toolId));
          },
        }
      );

      // TEXT_MESSAGE_END 이벤트 전송
      sendAGUIEvent(createTextMessageEnd(threadId, runId, messageId), response);

      // RUN_FINISHED 이벤트 전송
      sendAGUIEvent(createRunFinished(threadId, runId), response);

    } catch (error) {
      log('error', `❌ Agent error: ${error}`);

      // RUN_ERROR 이벤트 전송
      const errorMessage = error instanceof Error ? error.message : String(error);
      sendAGUIEvent(
        createRunError(threadId, runId, errorMessage, 'AGENT_ERROR'),
        `죄송합니다. 오류가 발생했습니다: ${error}`
      );
    }
  }

  /**
   * 특정 클라이언트에게 메시지 전송
   */
  send(clientId: string, message: GatewayMessage): void {
    const client = this.clients.get(clientId);
    
    if (!client) {
      log('warn', `⚠️ Client not found: ${clientId}`);
      return;
    }

    if (client.ws.readyState !== WebSocket.OPEN) {
      log('warn', `⚠️ Client not ready: ${clientId}`);
      return;
    }

    try {
      client.ws.send(JSON.stringify(message));
      log('debug', `📤 Message sent to ${clientId}: ${message.from} -> ${message.to}`);
    } catch (error) {
      log('error', `❌ Failed to send message to ${clientId}: ${error}`);
    }
  }

  /**
   * 모든 클라이언트에게 브로드캐스트
   */
  broadcast(message: GatewayMessage): void {
    log('debug', `📣 Broadcasting message: ${message.from} -> ${message.to}`);
    
    this.clients.forEach((client) => {
      if (client.ws.readyState === WebSocket.OPEN) {
        client.ws.send(JSON.stringify(message));
      }
    });
  }

  /**
   * 특정 타입의 클라이언트 찾기
   */
  private findClientByType(type: string): Client | undefined {
    for (const client of this.clients.values()) {
      if (client.type === type) {
        return client;
      }
    }
    return undefined;
  }

  /**
   * 클라이언트 ID 생성
   */
  private generateClientId(): string {
    return `client_${Date.now()}_${Math.random().toString(36).substring(7)}`;
  }

  /**
   * 연결된 클라이언트 목록 조회
   */
  getClients(): Array<{ id: string; type: string; connectedAt: number }> {
    return Array.from(this.clients.values()).map((client) => ({
      id: client.id,
      type: client.type,
      connectedAt: client.connectedAt,
    }));
  }

  /**
   * Gateway 서버 종료
   */
  async close(): Promise<void> {
    return new Promise((resolve) => {
      if (!this.wss) {
        resolve();
        return;
      }

      log('info', '👋 Closing Gateway...');

      // 모든 클라이언트 연결 종료
      this.clients.forEach((client) => {
        client.ws.close();
      });
      this.clients.clear();

      // 서버 종료
      this.wss.close(() => {
        log('info', '✅ Gateway closed');
        resolve();
      });
    });
  }
}
