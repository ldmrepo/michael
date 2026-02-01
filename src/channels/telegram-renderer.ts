/**
 * Telegram Adaptive Renderer
 *
 * Converts A2UI components to Telegram-native messages.
 * If complex form inputs are detected, returns a Web App button instead.
 *
 * @see https://core.telegram.org/bots/api
 */

import {
  ComponentDefinition,
  SurfaceUpdate,
  BoundValue,
  Action,
  ExplicitList,
  isTextComponent,
  isButtonComponent,
  isImageComponent,
  isCardComponent,
  isRowComponent,
  isColumnComponent,
  isListComponent,
  isListItemComponent,
  isDividerComponent,
  isSpacerComponent,
  isFormInputComponent,
} from '../a2ui/types.js';
import { log } from '../utils/logger.js';

// --- Telegram Types ---

/**
 * Telegram InlineKeyboardButton
 */
export interface InlineKeyboardButton {
  text: string;
  callback_data?: string;
  url?: string;
  web_app?: { url: string };
}

/**
 * Telegram InlineKeyboardMarkup
 */
export interface InlineKeyboardMarkup {
  inline_keyboard: InlineKeyboardButton[][];
}

/**
 * Telegram message options
 */
export interface TelegramMessageOptions {
  parse_mode?: 'Markdown' | 'MarkdownV2' | 'HTML';
  reply_markup?: InlineKeyboardMarkup;
  disable_web_page_preview?: boolean;
}

/**
 * Rendered Telegram message
 */
export interface TelegramRenderedMessage {
  text: string;
  options: TelegramMessageOptions;
  /** Additional images to send separately */
  images?: Array<{ url: string; caption?: string }>;
  /** Whether to open Web App for complex forms */
  requiresWebApp?: boolean;
  webAppUrl?: string;
}

// --- Renderer Configuration ---

export interface TelegramRendererConfig {
  /** Web App base URL for complex forms */
  webAppBaseUrl?: string;
  /** Maximum buttons per row */
  maxButtonsPerRow?: number;
  /** Maximum inline keyboard rows */
  maxKeyboardRows?: number;
  /** Session storage for A2UI state */
  sessionStore?: A2UISessionStore;
}

/**
 * Interface for storing A2UI state for Web App sessions
 */
export interface A2UISessionStore {
  set(sessionId: string, surface: SurfaceUpdate, ttlMs?: number): void;
  get(sessionId: string): SurfaceUpdate | undefined;
  delete(sessionId: string): void;
}

// --- In-Memory Session Store ---

/**
 * Simple in-memory session store with TTL
 */
export class InMemorySessionStore implements A2UISessionStore {
  private sessions = new Map<string, { surface: SurfaceUpdate; expiresAt: number }>();
  private cleanupInterval: NodeJS.Timeout | null = null;
  private defaultTtlMs = 30 * 60 * 1000; // 30 minutes

  constructor() {
    // Cleanup expired sessions every 5 minutes
    this.cleanupInterval = setInterval(() => this.cleanup(), 5 * 60 * 1000);
  }

  set(sessionId: string, surface: SurfaceUpdate, ttlMs?: number): void {
    const expiresAt = Date.now() + (ttlMs || this.defaultTtlMs);
    this.sessions.set(sessionId, { surface, expiresAt });
  }

  get(sessionId: string): SurfaceUpdate | undefined {
    const entry = this.sessions.get(sessionId);
    if (!entry) return undefined;
    if (Date.now() > entry.expiresAt) {
      this.sessions.delete(sessionId);
      return undefined;
    }
    return entry.surface;
  }

  delete(sessionId: string): void {
    this.sessions.delete(sessionId);
  }

  private cleanup(): void {
    const now = Date.now();
    for (const [id, entry] of this.sessions) {
      if (now > entry.expiresAt) {
        this.sessions.delete(id);
      }
    }
  }

  destroy(): void {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
      this.cleanupInterval = null;
    }
    this.sessions.clear();
  }
}

// --- Telegram Adaptive Renderer ---

/**
 * Telegram Adaptive Renderer
 *
 * Converts A2UI SurfaceUpdate to Telegram-native messages.
 * Falls back to Web App for complex forms.
 *
 * @example
 * ```ts
 * const renderer = new TelegramAdaptiveRenderer({
 *   webAppBaseUrl: 'https://michael.app/webapp',
 * });
 *
 * const result = renderer.render(surfaceUpdate, dataModel);
 * if (result.requiresWebApp) {
 *   // Open Telegram Web App
 * } else {
 *   // Send native Telegram message
 * }
 * ```
 */
export class TelegramAdaptiveRenderer {
  private config: Required<TelegramRendererConfig>;
  private componentMap = new Map<string, ComponentDefinition>();

  constructor(config: TelegramRendererConfig = {}) {
    this.config = {
      webAppBaseUrl: config.webAppBaseUrl || '',
      maxButtonsPerRow: config.maxButtonsPerRow || 3,
      maxKeyboardRows: config.maxKeyboardRows || 8,
      sessionStore: config.sessionStore || new InMemorySessionStore(),
    };
  }

  /**
   * Render A2UI SurfaceUpdate to Telegram message (v0.8 standard)
   */
  render(
    surface: SurfaceUpdate,
    dataModel?: Record<string, unknown>
  ): TelegramRenderedMessage {
    const { components } = surface.surfaceUpdate;

    // Build component map for ID lookup
    this.componentMap.clear();
    for (const comp of components) {
      this.componentMap.set(comp.id, comp);
    }

    // Check if any form inputs exist
    const hasFormInputs = components.some((c: ComponentDefinition) =>
      isFormInputComponent(c.component)
    );

    if (hasFormInputs && this.config.webAppBaseUrl) {
      return this.renderWithWebApp(surface);
    }

    // Native rendering
    return this.renderNative(components, dataModel);
  }

  /**
   * Render with Web App fallback for complex forms
   */
  private renderWithWebApp(surface: SurfaceUpdate): TelegramRenderedMessage {
    const sessionId = this.generateSessionId();
    this.config.sessionStore.set(sessionId, surface);

    const webAppUrl = `${this.config.webAppBaseUrl}?session=${sessionId}`;

    return {
      text: '📝 입력이 필요합니다. 아래 버튼을 눌러주세요.',
      options: {
        reply_markup: {
          inline_keyboard: [
            [
              {
                text: '📝 폼 열기',
                web_app: { url: webAppUrl },
              },
            ],
          ],
        },
      },
      requiresWebApp: true,
      webAppUrl,
    };
  }

  /**
   * Render components natively to Telegram
   */
  private renderNative(
    components: ComponentDefinition[],
    dataModel?: Record<string, unknown>
  ): TelegramRenderedMessage {
    let text = '';
    const buttons: InlineKeyboardButton[][] = [];
    const images: Array<{ url: string; caption?: string }> = [];
    let currentButtonRow: InlineKeyboardButton[] = [];

    for (const def of components) {
      const rendered = this.renderComponent(def, dataModel);

      if (rendered.text) {
        text += rendered.text;
      }

      if (rendered.button) {
        currentButtonRow.push(rendered.button);
        if (currentButtonRow.length >= this.config.maxButtonsPerRow) {
          buttons.push(currentButtonRow);
          currentButtonRow = [];
        }
      }

      if (rendered.image) {
        images.push(rendered.image);
      }
    }

    // Push remaining buttons
    if (currentButtonRow.length > 0) {
      buttons.push(currentButtonRow);
    }

    // Trim to max keyboard rows
    const finalButtons = buttons.slice(0, this.config.maxKeyboardRows);

    return {
      text: text.trim() || '메시지가 없습니다.',
      options: {
        parse_mode: 'Markdown',
        reply_markup: finalButtons.length > 0 ? { inline_keyboard: finalButtons } : undefined,
        disable_web_page_preview: true,
      },
      images: images.length > 0 ? images : undefined,
    };
  }

  /**
   * Render a single component
   */
  private renderComponent(
    def: ComponentDefinition,
    dataModel?: Record<string, unknown>
  ): { text?: string; button?: InlineKeyboardButton; image?: { url: string; caption?: string } } {
    const c = def.component;

    // Text component
    if (isTextComponent(c)) {
      const content = this.resolveBoundValue(c.Text.text, dataModel);
      const usage = c.Text.usageHint;

      switch (usage) {
        case 'h1':
          return { text: `*${this.escapeMarkdown(content)}*\n\n` };
        case 'h2':
          return { text: `*${this.escapeMarkdown(content)}*\n` };
        case 'h3':
          return { text: `_${this.escapeMarkdown(content)}_\n` };
        case 'caption':
          return { text: `_${this.escapeMarkdown(content)}_\n` };
        default:
          return { text: `${this.escapeMarkdown(content)}\n` };
      }
    }

    // Button component
    if (isButtonComponent(c)) {
      const label = this.resolveBoundValue(c.Button.label, dataModel);
      const action = c.Button.action;
      const callbackData = this.serializeAction(action);

      return {
        button: {
          text: label,
          callback_data: callbackData.substring(0, 64), // Telegram limit
        },
      };
    }

    // Image component
    if (isImageComponent(c)) {
      const src = this.resolveBoundValue(c.Image.src, dataModel);
      const alt = c.Image.alt ? this.resolveBoundValue(c.Image.alt, dataModel) : undefined;

      return {
        image: { url: src, caption: alt },
      };
    }

    // Card component
    if (isCardComponent(c)) {
      const title = this.resolveBoundValue(c.Card.title, dataModel);
      const subtitle = c.Card.subtitle
        ? this.resolveBoundValue(c.Card.subtitle, dataModel)
        : '';

      let text = `━━━━━━━━━━━━━━━\n*${this.escapeMarkdown(title)}*\n`;
      if (subtitle) {
        text += `_${this.escapeMarkdown(subtitle)}_\n`;
      }

      // Render children
      const childIds = this.resolveChildIds(c.Card.children, dataModel);
      for (const childId of childIds) {
        const child = this.componentMap.get(childId);
        if (child) {
          const childRendered = this.renderComponent(child, dataModel);
          if (childRendered.text) {
            text += childRendered.text;
          }
        }
      }

      return { text };
    }

    // Row/Column component - render children
    if (isRowComponent(c) || isColumnComponent(c)) {
      const children = isRowComponent(c) ? c.Row.children : c.Column.children;
      const childIds = this.resolveChildIds(children, dataModel);

      let text = '';
      for (const childId of childIds) {
        const child = this.componentMap.get(childId);
        if (child) {
          const childRendered = this.renderComponent(child, dataModel);
          if (childRendered.text) {
            text += childRendered.text;
          }
        }
      }

      return { text };
    }

    // List component
    if (isListComponent(c)) {
      const childIds = this.resolveChildIds(c.List.children, dataModel);
      const style = c.List.style || 'bullet';

      let text = '';
      let index = 1;

      for (const childId of childIds) {
        const child = this.componentMap.get(childId);
        if (child && isListItemComponent(child.component)) {
          const content = this.resolveBoundValue(child.component.ListItem.content, dataModel);
          const prefix = style === 'number' ? `${index}. ` : style === 'bullet' ? '• ' : '';
          text += `${prefix}${this.escapeMarkdown(content)}\n`;
          index++;
        }
      }

      return { text };
    }

    // ListItem component (standalone)
    if (isListItemComponent(c)) {
      const content = this.resolveBoundValue(c.ListItem.content, dataModel);
      return { text: `• ${this.escapeMarkdown(content)}\n` };
    }

    // Divider component
    if (isDividerComponent(c)) {
      return { text: '───────────────\n' };
    }

    // Spacer component
    if (isSpacerComponent(c)) {
      return { text: '\n' };
    }

    // Unknown or form input - skip
    log('debug', `Skipping unsupported component: ${def.id}`);
    return {};
  }

  /**
   * Resolve BoundValue to string (v0.8 standard)
   */
  private resolveBoundValue(
    value: BoundValue,
    dataModel?: Record<string, unknown>
  ): string {
    // Check literal values first
    if (value.literalString !== undefined) {
      return value.literalString;
    }
    if (value.literalNumber !== undefined) {
      return String(value.literalNumber);
    }
    if (value.literalBoolean !== undefined) {
      return String(value.literalBoolean);
    }

    if (!value.path || !dataModel) {
      return '';
    }

    // Path resolution
    const path = value.path.startsWith('/') ? value.path.slice(1) : value.path;
    const parts = path.split('/');
    let current: unknown = dataModel;

    for (const part of parts) {
      if (current && typeof current === 'object' && part in current) {
        current = (current as Record<string, unknown>)[part];
      } else {
        return '';
      }
    }

    return String(current ?? '');
  }

  /**
   * Resolve child IDs from ExplicitList or PathReference
   */
  private resolveChildIds(
    children: ExplicitList | { path: string },
    dataModel?: Record<string, unknown>
  ): string[] {
    if ('explicitList' in children) {
      return children.explicitList;
    }

    // Path reference - resolve from data model
    if (!dataModel) return [];

    const resolved = this.resolveBoundValue(children, dataModel);
    if (Array.isArray(resolved)) {
      return resolved.map(String);
    }

    return [];
  }

  /**
   * Serialize action to callback_data string (v0.8 standard)
   */
  private serializeAction(action: Action): string {
    // Format: action_name:key1=val1,key2=val2
    let data = action.name;

    if (action.context && action.context.length > 0) {
      const contextParts = action.context.map((ctx) => {
        // v0.8: BoundValue has literalString, literalNumber, literalBoolean, or path
        const val = ctx.value.literalString ?? ctx.value.literalNumber ?? ctx.value.literalBoolean ?? ctx.value.path ?? '';
        return `${ctx.key}=${val}`;
      });
      data += ':' + contextParts.join(',');
    }

    return data;
  }

  /**
   * Parse callback_data back to Action
   */
  parseCallbackData(callbackData: string): Action {
    const colonIndex = callbackData.indexOf(':');
    if (colonIndex === -1) {
      return { name: callbackData };
    }

    const name = callbackData.substring(0, colonIndex);
    const contextStr = callbackData.substring(colonIndex + 1);
    const context = contextStr.split(',').map((pair) => {
      const [key, value] = pair.split('=');
      return {
        key,
        value: { literalString: value || '' },
      };
    });

    return { name, context };
  }

  /**
   * Escape Markdown special characters
   */
  private escapeMarkdown(text: string): string {
    // Telegram Markdown escaping (basic mode)
    return text
      .replace(/\*/g, '\\*')
      .replace(/_/g, '\\_')
      .replace(/\[/g, '\\[')
      .replace(/\]/g, '\\]')
      .replace(/`/g, '\\`');
  }

  /**
   * Generate a unique session ID
   */
  private generateSessionId(): string {
    return `tg_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }

  /**
   * Get session store (for Web App integration)
   */
  getSessionStore(): A2UISessionStore {
    return this.config.sessionStore;
  }
}

// --- Factory Function ---

/**
 * Create a TelegramAdaptiveRenderer instance
 */
export function createTelegramRenderer(config?: TelegramRendererConfig): TelegramAdaptiveRenderer {
  return new TelegramAdaptiveRenderer(config);
}

// --- Utility Functions ---

/**
 * Check if A2UI surface requires Web App for rendering (v0.8 standard)
 */
export function requiresWebApp(surface: SurfaceUpdate): boolean {
  return surface.surfaceUpdate.components.some((c: ComponentDefinition) => isFormInputComponent(c.component));
}
