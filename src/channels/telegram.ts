import { Telegraf } from 'telegraf';
import WebSocket from 'ws';
import { GatewayMessage } from '../core/gateway.js';
import { log } from '../utils/logger.js';
import {
  TelegramAdaptiveRenderer,
  TelegramRendererConfig,
  TelegramRenderedMessage,
} from './telegram-renderer.js';
import { TelegramWebAppManager } from './telegram-webapp.js';
import { SurfaceUpdate } from '../a2ui/types.js';
import { A2UI_MIME_TYPE } from '../core/a2ui.js';

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
  // 타이핑 인디케이터 관리 (AG-UI)
  private typingIntervals: Map<string, NodeJS.Timeout> = new Map();
  // A2UI 적응형 렌더러
  private renderer: TelegramAdaptiveRenderer;
  // Web App 매니저
  private webAppManager: TelegramWebAppManager | null = null;

  constructor(token: string, gatewayUrl: string, rendererConfig?: TelegramRendererConfig) {
    this.bot = new Telegraf(token);
    this.gatewayUrl = gatewayUrl;
    this.renderer = new TelegramAdaptiveRenderer(rendererConfig);
    this.setupBotHandlers();
  }

  /**
   * 시작
   */
  async start(): Promise<void> {
    try {
      // Gateway 연결
      await this.connectToGateway();

      // Telegram 봇 시작 - long polling 방식
      log('info', '🚀 Starting Telegram bot polling...');

      // 이전 webhook 삭제
      await this.bot.telegram.deleteWebhook({ drop_pending_updates: false });
      log('info', '✅ Webhook cleared');

      // 수동 폴링 시작 (Telegraf launch()가 작동하지 않는 경우 대비)
      this.startManualPolling();

      // 봇 정보 확인
      const botInfo = await this.bot.telegram.getMe();
      log('info', `✅ Telegram bot ready: @${botInfo.username}`);

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

      // AG-UI 이벤트 타입이 있으면 AG-UI 핸들러로 위임
      if (message.eventType) {
        this.handleAGUIEvent(message, chatId);
        return;
      }

      // 레거시: 단순 메시지 전송
      this.sendMessage(chatId, message.content);

    } catch (error) {
      log('error', `❌ Failed to handle Gateway message: ${error}`);
    }
  }

  /**
   * AG-UI 이벤트 처리
   */
  private handleAGUIEvent(message: GatewayMessage, chatId: number): void {
    switch (message.eventType) {
      case 'RUN_STARTED':
        // 타이핑 인디케이터 시작
        this.startTypingIndicator(chatId);
        log('debug', `🏃 Run started for chat ${chatId}, runId: ${message.runId}`);
        break;

      case 'TEXT_MESSAGE_START':
        // 메시지 생성 시작 (현재는 로깅만)
        log('debug', `📝 Text message start for chat ${chatId}, messageId: ${message.messageId}`);
        break;

      case 'TEXT_MESSAGE_CONTENT':
        // 스트리밍 콘텐츠 (Telegram에서는 최종 메시지만 전송하므로 무시)
        log('debug', `📝 Text content delta for chat ${chatId}`);
        break;

      case 'TEXT_MESSAGE_END':
        // 메시지 완료 - 실제 메시지 전송
        this.stopTypingIndicator(chatId);
        if (message.content) {
          this.sendMessage(chatId, message.content);
        }
        log('debug', `✅ Text message end for chat ${chatId}`);
        break;

      case 'TOOL_CALL_START':
        // 도구 호출 시작 (타이핑 유지)
        log('debug', `🔧 Tool call start: ${message.toolCallName}`);
        break;

      case 'TOOL_CALL_END':
        // 도구 호출 완료
        log('debug', `🔧 Tool call end: ${message.toolCallId}`);
        break;

      case 'RUN_FINISHED':
        // 실행 완료
        this.stopTypingIndicator(chatId);
        log('debug', `🏁 Run finished for chat ${chatId}, runId: ${message.runId}`);
        break;

      case 'RUN_ERROR':
        // 오류 발생
        this.stopTypingIndicator(chatId);
        this.sendMessage(chatId, '❌ 죄송합니다. 오류가 발생했습니다.');
        log('error', `❌ Run error for chat ${chatId}: ${message.errorMessage}`);
        break;

      case 'TOOL_CALL_RESULT':
        // A2UI 렌더링 결과 처리
        if (message.metadata?.mimeType === A2UI_MIME_TYPE) {
          this.handleA2UIMessage(message, chatId);
        }
        break;

      default:
        log('warn', `⚠️ Unknown AG-UI event type: ${message.eventType}`);
    }
  }

  /**
   * A2UI 메시지 처리 및 Telegram 렌더링
   */
  private async handleA2UIMessage(message: GatewayMessage, chatId: number): Promise<void> {
    try {
      const a2uiData = message.metadata?.a2ui as SurfaceUpdate | undefined;
      if (!a2uiData || !('surfaceUpdate' in a2uiData)) {
        log('warn', '⚠️ Invalid A2UI message');
        return;
      }

      // A2UI를 Telegram 메시지로 변환
      const dataModel = message.metadata?.dataModel as Record<string, unknown> | undefined;
      const rendered = this.renderer.render(a2uiData, dataModel);

      // 이미지 먼저 전송
      if (rendered.images && rendered.images.length > 0) {
        for (const img of rendered.images) {
          await this.sendPhoto(chatId, img.url, img.caption);
        }
      }

      // Web App이 필요한 경우 세션 생성 및 Mini App 버튼 전송
      if (rendered.requiresWebApp && this.webAppManager) {
        const session = this.webAppManager.createSession(
          message.userId,
          chatId,
          a2uiData,
          dataModel || {}
        );

        const webappUrl = process.env.WEBAPP_URL || 'https://roxy-exoskeletal-shayla.ngrok-free.dev';
        const sessionUrl = `${webappUrl}/webapp/?session=${session.sessionId}`;

        // 텍스트와 함께 Mini App 버튼 전송
        await this.bot.telegram.sendMessage(chatId, rendered.text || '📝 아래 버튼을 눌러 폼을 작성해주세요:', {
          parse_mode: 'Markdown',
          reply_markup: {
            inline_keyboard: [[
              {
                text: '📝 폼 열기',
                web_app: { url: sessionUrl }
              }
            ]]
          }
        });

        log('info', `📱 Mini App session created: ${session.sessionId} for chat ${chatId}`);
      } else {
        // 일반 텍스트 메시지 전송
        await this.sendMessageWithOptions(chatId, rendered);
      }

      log('debug', `✅ A2UI rendered for chat ${chatId}, requiresWebApp: ${rendered.requiresWebApp}`);
    } catch (error) {
      log('error', `❌ Failed to handle A2UI message: ${error}`);
    }
  }

  /**
   * 옵션과 함께 Telegram 메시지 전송
   */
  private async sendMessageWithOptions(chatId: number, rendered: TelegramRenderedMessage): Promise<void> {
    try {
      await this.bot.telegram.sendMessage(chatId, rendered.text, {
        parse_mode: rendered.options.parse_mode,
        // Cast to any to handle type incompatibility between our types and Telegraf's
        reply_markup: rendered.options.reply_markup as any,
        link_preview_options: rendered.options.disable_web_page_preview
          ? { is_disabled: true }
          : undefined,
      });
    } catch (error) {
      log('error', `❌ Failed to send Telegram message with options: ${error}`);
    }
  }

  /**
   * Telegram으로 이미지 전송
   */
  private async sendPhoto(chatId: number, url: string, caption?: string): Promise<void> {
    try {
      await this.bot.telegram.sendPhoto(chatId, url, { caption });
    } catch (error) {
      log('error', `❌ Failed to send Telegram photo: ${error}`);
    }
  }

  /**
   * 타이핑 인디케이터 시작
   */
  private startTypingIndicator(chatId: number): void {
    const chatKey = String(chatId);

    // 이미 타이핑 중이면 무시
    if (this.typingIntervals.has(chatKey)) {
      return;
    }

    // 즉시 타이핑 액션 전송
    this.bot.telegram.sendChatAction(chatId, 'typing').catch((err) => {
      log('error', `❌ Failed to send typing action: ${err}`);
    });

    // 4초마다 타이핑 액션 반복 (Telegram 타이핑 인디케이터는 5초 후 사라짐)
    const interval = setInterval(() => {
      this.bot.telegram.sendChatAction(chatId, 'typing').catch((err) => {
        log('error', `❌ Failed to send typing action: ${err}`);
      });
    }, 4000);

    this.typingIntervals.set(chatKey, interval);
    log('debug', `⌨️ Started typing indicator for chat ${chatId}`);
  }

  /**
   * 타이핑 인디케이터 중지
   */
  private stopTypingIndicator(chatId: number): void {
    const chatKey = String(chatId);
    const interval = this.typingIntervals.get(chatKey);

    if (interval) {
      clearInterval(interval);
      this.typingIntervals.delete(chatKey);
      log('debug', `⌨️ Stopped typing indicator for chat ${chatId}`);
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

    // /webapp 명령어 - Mini App을 Inline Button으로 열기 (데모)
    this.bot.command('webapp', async (ctx) => {
      const webappUrl = process.env.WEBAPP_URL || 'https://roxy-exoskeletal-shayla.ngrok-free.dev';
      
      await ctx.reply('📱 Mini App을 열어보세요:', {
        reply_markup: {
          inline_keyboard: [[
            {
              text: '📝 폼 열기',
              web_app: { url: `${webappUrl}/webapp/` }
            }
          ]]
        }
      });
      
      log('info', `📱 Webapp button sent to: ${ctx.from?.id}`);
    });

    // /form 명령어 - 실제 세션 기반 A2UI 폼 테스트
    this.bot.command('form', async (ctx) => {
      const userId = ctx.from.id.toString();
      const chatId = ctx.chat.id;

      if (!this.webAppManager) {
        await ctx.reply('❌ WebAppManager가 연결되지 않았습니다.');
        return;
      }

      // 테스트용 A2UI Surface 생성 (v0.8 standard)
      const testSurface: SurfaceUpdate = {
        surfaceUpdate: {
          surfaceId: 'reservation-form',
          components: [
            {
              id: 'title',
              component: {
                Text: {
                  text: { literalString: '예약 정보 입력' },
                  usageHint: 'h1',
                },
              },
            },
            {
              id: 'name-input',
              component: {
                TextField: {
                  label: { literalString: '이름' },
                  value: { path: '/form/name' },
                  placeholder: { literalString: '이름을 입력하세요' },
                  required: true,
                },
              },
            },
            {
              id: 'phone-input',
              component: {
                TextField: {
                  label: { literalString: '전화번호' },
                  value: { path: '/form/phone' },
                  placeholder: { literalString: '010-0000-0000' },
                  required: true,
                },
              },
            },
            {
              id: 'date-input',
              component: {
                DateTimeInput: {
                  label: { literalString: '예약 날짜' },
                  value: { path: '/form/date' },
                  mode: 'date',
                  required: true,
                },
              },
            },
            {
              id: 'submit-btn',
              component: {
                Button: {
                  label: { literalString: '예약하기' },
                  action: { name: 'submit_reservation' },
                  variant: 'primary',
                },
              },
            },
          ],
        },
      };

      // 세션 생성
      const session = this.webAppManager.createSession(userId, chatId, testSurface, {});
      const webappUrl = process.env.WEBAPP_URL || 'https://roxy-exoskeletal-shayla.ngrok-free.dev';
      const sessionUrl = `${webappUrl}/webapp/?session=${session.sessionId}`;

      // Mini App 버튼과 함께 메시지 전송 (Reply Keyboard 사용 - sendData가 message로 전달됨)
      await ctx.reply('📝 아래 버튼을 눌러 예약 폼을 작성해주세요:', {
        reply_markup: {
          keyboard: [[
            {
              text: '📝 예약 폼 열기',
              web_app: { url: sessionUrl }
            }
          ]],
          resize_keyboard: true,
          one_time_keyboard: true,
        }
      });

      log('info', `📱 Form session created: ${session.sessionId} for user ${userId}`);
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

    // 콜백 쿼리 핸들러 (인라인 버튼 클릭)
    this.bot.on('callback_query', async (ctx) => {
      const callbackQuery = ctx.callbackQuery;
      if (!('data' in callbackQuery)) return;

      const userId = ctx.from.id.toString();
      const chatId = callbackQuery.message?.chat.id;
      const callbackData = callbackQuery.data;

      if (!chatId) return;

      log('debug', `🔘 Callback query from ${userId}: ${callbackData}`);

      // 콜백 응답 (버튼 로딩 상태 해제)
      await ctx.answerCbQuery();

      // 액션 파싱
      const action = this.renderer.parseCallbackData(callbackData);

      // Gateway로 액션 전송
      this.sendToGateway({
        from: 'telegram',
        to: 'agent',
        userId,
        content: `[ACTION:${action.name}]`,
        metadata: {
          chatId,
          action: action,
          type: 'callback_query',
        },
      });
    });

    // Web App 데이터 수신 핸들러 (message 이벤트로 web_app_data 감지)
    this.bot.on('message', async (ctx) => {
      const message = ctx.message as any;

      // web_app_data 메시지인지 확인
      if (message.web_app_data) {
        const userId = ctx.from.id.toString();
        const chatId = ctx.chat.id;
        const webAppData = message.web_app_data;

        log('info', `📱 Web App data received from ${userId}: ${webAppData.data}`);

        try {
          const data = JSON.parse(webAppData.data);

          // Gateway로 Web App 결과 전송
          this.sendToGateway({
            from: 'telegram',
            to: 'agent',
            userId,
            content: `[WEBAPP_RESULT]`,
            metadata: {
              chatId,
              webAppData: data,
              type: 'web_app_data',
            },
          });
        } catch (error) {
          log('error', `❌ Failed to parse Web App data: ${error}`);
        }
      }
    });

    // 에러 핸들러
    this.bot.catch((error: any) => {
      log('error', `❌ Telegram bot error: ${error}`);
    });
  }

  /**
   * 수동 long polling 시작 (Telegraf launch() 대안)
   */
  private startManualPolling(): void {
    let offset = 0;
    let running = true;

    const poll = async () => {
      while (running) {
        try {
          const updates = await this.bot.telegram.callApi('getUpdates', {
            offset,
            timeout: 30,
            allowed_updates: ['message', 'callback_query'],
          }) as any[];

          for (const update of updates) {
            offset = update.update_id + 1;
            log('debug', `📩 Processing update: ${update.update_id}`);
            try {
              await this.bot.handleUpdate(update);
            } catch (err: any) {
              log('error', `❌ Error handling update: ${err.message}`);
            }
          }
        } catch (err: any) {
          log('error', `❌ Polling error: ${err.message}`);
          await new Promise(resolve => setTimeout(resolve, 5000)); // 5초 대기 후 재시도
        }
      }
    };

    poll().catch((err) => {
      log('error', `❌ Manual polling stopped: ${err.message}`);
    });

    log('info', '✅ Manual polling started');
  }

  /**
   * A2UI 렌더러 접근
   */
  getRenderer(): TelegramAdaptiveRenderer {
    return this.renderer;
  }


  /**
   * Set the WebAppManager for Mini App integration
   */
  setWebAppManager(manager: TelegramWebAppManager): void {
    this.webAppManager = manager;
    log('info', '📱 WebAppManager connected to Telegram channel');
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

    // 모든 타이핑 인디케이터 정리
    for (const [, interval] of this.typingIntervals) {
      clearInterval(interval);
    }
    this.typingIntervals.clear();

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
