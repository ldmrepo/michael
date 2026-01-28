import { Telegraf } from 'telegraf';
import WebSocket from 'ws';
import { GatewayMessage } from '../core/gateway.js';
import { log } from '../utils/logger.js';

/**
 * Telegram 메시지 메타데이터
 */
interface TelegramMetadata {
  chatId: number;
  messageId: number;
  username?: string;
  firstName?: string;
  lastName?: string;
}

/**
 * Telegram Channel
 * Telegraf 봇으로 메시지 송수신 및 Gateway 연결
 */
export class TelegramChannel {
  private bot: Telegraf;
  private gateway: WebSocket | null = null;
  private gatewayUrl: string;
  private reconnectInterval: NodeJS.Timeout | null = null;
  private isConnected = false;

  constructor(token: string, gatewayUrl: string) {
    this.bot = new Telegraf(token);
    this.gatewayUrl = gatewayUrl;
    this.setupBotHandlers();
  }

  /**
   * 시작
   */
  async start(): Promise<void> {
    try {
      // Gateway 연결
      await this.connectToGateway();

      // Telegram 봇 시작
      await this.bot.launch();

      log('info', '✅ Telegram channel started');

    } catch (error) {
      log('error', `❌ Failed to start Telegram channel: ${error}`);
      throw error;
    }
  }

  /**
   * Gateway 연결
   */
  private async connectToGateway(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.gateway = new WebSocket(this.gatewayUrl);

        this.gateway.on('open', () => {
          log('info', '🔌 Connected to Gateway');
          this.isConnected = true;

          // 재연결 타이머 정리
          if (this.reconnectInterval) {
            clearInterval(this.reconnectInterval);
            this.reconnectInterval = null;
          }

          resolve();
        });

        this.gateway.on('message', (data) => {
          this.handleGatewayMessage(data);
        });

        this.gateway.on('close', () => {
          log('warn', '⚠️ Gateway connection closed');
          this.isConnected = false;
          this.scheduleReconnect();
        });

        this.gateway.on('error', (error) => {
          log('error', `❌ Gateway connection error: ${error.message}`);
          this.isConnected = false;
          reject(error);
        });

      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * Gateway 재연결 스케줄
   */
  private scheduleReconnect(): void {
    if (this.reconnectInterval) return;

    log('info', '🔄 Scheduling Gateway reconnect...');
    
    this.reconnectInterval = setInterval(() => {
      if (!this.isConnected) {
        log('info', '🔄 Attempting to reconnect to Gateway...');
        this.connectToGateway().catch((error) => {
          log('error', `❌ Reconnect failed: ${error.message}`);
        });
      }
    }, 5000); // 5초마다 재연결 시도
  }

  /**
   * Gateway 메시지 처리
   */
  private handleGatewayMessage(data: WebSocket.Data): void {
    try {
      const message: GatewayMessage = JSON.parse(data.toString());

      // Telegram으로 향하는 메시지만 처리
      if (message.to !== 'telegram') return;

      log('debug', `📥 Gateway message: ${message.from} -> telegram`);

      // 메타데이터에서 chatId 추출
      const chatId = message.metadata?.chatId;
      if (!chatId) {
        log('warn', '⚠️ No chatId in metadata');
        return;
      }

      // Telegram으로 메시지 전송
      this.sendMessage(chatId, message.content);

    } catch (error) {
      log('error', `❌ Failed to handle Gateway message: ${error}`);
    }
  }

  /**
   * Gateway로 메시지 전송
   */
  private sendToGateway(message: GatewayMessage): void {
    if (!this.gateway || !this.isConnected) {
      log('warn', '⚠️ Gateway not connected');
      return;
    }

    try {
      this.gateway.send(JSON.stringify(message));
      log('debug', `📤 Sent to Gateway: telegram -> ${message.to}`);
    } catch (error) {
      log('error', `❌ Failed to send to Gateway: ${error}`);
    }
  }

  /**
   * Telegram 봇 핸들러 설정
   */
  private setupBotHandlers(): void {
    // /start 명령어
    this.bot.command('start', async (ctx) => {
      const welcomeMessage = `
안녕하세요! 저는 마이클입니다. 🤖

저는 24시간 깨어있으며, 모든 대화를 기억합니다.
무엇을 도와드릴까요?

💡 명령어:
/help - 도움말 보기
/remember <내용> - 중요한 정보 기억
/recall <검색어> - 기억 검색
/schedule <시간> <메시지> - 알림 설정

그냥 대화하셔도 됩니다! 😊
      `.trim();

      await ctx.reply(welcomeMessage);
      log('info', `👋 User started: ${ctx.from?.id}`);
    });

    // /help 명령어
    this.bot.command('help', async (ctx) => {
      const helpMessage = `
📖 마이클 사용 가이드

**기본 대화**
그냥 메시지를 보내면 제가 응답합니다.

**명령어**
/remember <내용> - 중요한 정보를 기억합니다
/recall <검색어> - 저장된 정보를 검색합니다
/schedule <시간> <메시지> - 특정 시간에 알림을 보냅니다

**예시**
"내 생일은 3월 15일이야"
"매일 오전 9시에 날씨 알려줘"
"내 생일이 언제야?"

궁금한 점이 있으시면 언제든 물어보세요!
      `.trim();

      await ctx.reply(helpMessage);
    });

    // 일반 텍스트 메시지
    this.bot.on('text', async (ctx) => {
      const userId = ctx.from.id.toString();
      const message = ctx.message.text;
      const chatId = ctx.chat.id;

      log('debug', `💬 Message from ${userId}: ${message}`);

      // Gateway로 전송
      this.sendToGateway({
        from: 'telegram',
        to: 'agent',
        userId,
        content: message,
        metadata: {
          chatId,
          messageId: ctx.message.message_id,
          username: ctx.from.username,
          firstName: ctx.from.first_name,
          lastName: ctx.from.last_name,
        } as TelegramMetadata,
      });

      // 타이핑 표시 (선택사항)
      await ctx.sendChatAction('typing');
    });

    // 에러 핸들러
    this.bot.catch((error: any) => {
      log('error', `❌ Telegram bot error: ${error}`);
    });
  }

  /**
   * Telegram으로 메시지 전송
   */
  async sendMessage(chatId: number, text: string): Promise<void> {
    try {
      await this.bot.telegram.sendMessage(chatId, text);
      log('debug', `📤 Sent to Telegram: ${chatId}`);
    } catch (error) {
      log('error', `❌ Failed to send Telegram message: ${error}`);
    }
  }

  /**
   * 종료
   */
  async stop(): Promise<void> {
    log('info', '👋 Stopping Telegram channel...');

    // 재연결 타이머 정리
    if (this.reconnectInterval) {
      clearInterval(this.reconnectInterval);
      this.reconnectInterval = null;
    }

    // Gateway 연결 종료
    if (this.gateway) {
      this.gateway.close();
      this.gateway = null;
    }

    // 봇 종료
    this.bot.stop();

    log('info', '✅ Telegram channel stopped');
  }
}
