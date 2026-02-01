/**
 * Telegram Adaptive Renderer Tests (v0.8 Standard)
 */

import { describe, it, expect, beforeEach } from 'vitest';
import {
  TelegramAdaptiveRenderer,
  InMemorySessionStore,
  requiresWebApp,
} from './telegram-renderer.js';
import { SurfaceUpdate, ComponentDefinition } from '../a2ui/types.js';

describe('TelegramAdaptiveRenderer (v0.8 Standard)', () => {
  let renderer: TelegramAdaptiveRenderer;

  beforeEach(() => {
    renderer = new TelegramAdaptiveRenderer({
      webAppBaseUrl: 'https://michael.app/webapp',
    });
  });

  describe('Text Components', () => {
    it('should render h1 text as bold with double newline', () => {
      const surface: SurfaceUpdate = {
        surfaceUpdate: {
          surfaceId: 'main',
          components: [
            {
              id: 'title',
              component: {
                Text: {
                  text: { literalString: 'Hello World' },
                  usageHint: 'h1',
                },
              },
            },
          ],
        },
      };

      const result = renderer.render(surface);
      expect(result.text).toContain('*Hello World*');
      expect(result.options.parse_mode).toBe('Markdown');
    });

    it('should render body text as plain text', () => {
      const surface: SurfaceUpdate = {
        surfaceUpdate: {
          surfaceId: 'main',
          components: [
            {
              id: 'body',
              component: {
                Text: {
                  text: { literalString: 'Plain text content' },
                },
              },
            },
          ],
        },
      };

      const result = renderer.render(surface);
      expect(result.text).toContain('Plain text content');
    });
  });

  describe('Button Components', () => {
    it('should render buttons as inline keyboard', () => {
      const surface: SurfaceUpdate = {
        surfaceUpdate: {
          surfaceId: 'main',
          components: [
            {
              id: 'btn1',
              component: {
                Button: {
                  label: { literalString: 'Click Me' },
                  action: { name: 'click_action' },
                },
              },
            },
          ],
        },
      };

      const result = renderer.render(surface);
      expect(result.options.reply_markup).toBeDefined();
      expect(result.options.reply_markup!.inline_keyboard).toHaveLength(1);
      expect(result.options.reply_markup!.inline_keyboard[0][0].text).toBe('Click Me');
      expect(result.options.reply_markup!.inline_keyboard[0][0].callback_data).toBe('click_action');
    });

    it('should limit buttons per row based on config', () => {
      const customRenderer = new TelegramAdaptiveRenderer({
        maxButtonsPerRow: 2,
      });

      const surface: SurfaceUpdate = {
        surfaceUpdate: {
          surfaceId: 'main',
          components: [
            { id: 'btn1', component: { Button: { label: { literalString: 'Btn1' }, action: { name: 'a1' } } } },
            { id: 'btn2', component: { Button: { label: { literalString: 'Btn2' }, action: { name: 'a2' } } } },
            { id: 'btn3', component: { Button: { label: { literalString: 'Btn3' }, action: { name: 'a3' } } } },
          ],
        },
      };

      const result = customRenderer.render(surface);
      expect(result.options.reply_markup!.inline_keyboard).toHaveLength(2);
      expect(result.options.reply_markup!.inline_keyboard[0]).toHaveLength(2);
      expect(result.options.reply_markup!.inline_keyboard[1]).toHaveLength(1);
    });
  });

  describe('Card Components', () => {
    it('should render card with title and divider', () => {
      const surface: SurfaceUpdate = {
        surfaceUpdate: {
          surfaceId: 'main',
          components: [
            {
              id: 'card1',
              component: {
                Card: {
                  title: { literalString: 'My Card' },
                  children: { explicitList: [] },
                },
              },
            },
          ],
        },
      };

      const result = renderer.render(surface);
      expect(result.text).toContain('━━━━');
      expect(result.text).toContain('*My Card*');
    });

    it('should render card with subtitle', () => {
      const surface: SurfaceUpdate = {
        surfaceUpdate: {
          surfaceId: 'main',
          components: [
            {
              id: 'card1',
              component: {
                Card: {
                  title: { literalString: 'Card Title' },
                  subtitle: { literalString: 'Card Subtitle' },
                  children: { explicitList: [] },
                },
              },
            },
          ],
        },
      };

      const result = renderer.render(surface);
      expect(result.text).toContain('*Card Title*');
      expect(result.text).toContain('_Card Subtitle_');
    });
  });

  describe('List Components', () => {
    it('should render bullet list', () => {
      const surface: SurfaceUpdate = {
        surfaceUpdate: {
          surfaceId: 'main',
          components: [
            {
              id: 'list1',
              component: {
                List: {
                  children: { explicitList: ['item1', 'item2'] },
                  style: 'bullet',
                },
              },
            },
            { id: 'item1', component: { ListItem: { content: { literalString: 'First' } } } },
            { id: 'item2', component: { ListItem: { content: { literalString: 'Second' } } } },
          ],
        },
      };

      const result = renderer.render(surface);
      expect(result.text).toContain('• First');
      expect(result.text).toContain('• Second');
    });

    it('should render numbered list', () => {
      const surface: SurfaceUpdate = {
        surfaceUpdate: {
          surfaceId: 'main',
          components: [
            {
              id: 'list1',
              component: {
                List: {
                  children: { explicitList: ['item1', 'item2'] },
                  style: 'number',
                },
              },
            },
            { id: 'item1', component: { ListItem: { content: { literalString: 'First' } } } },
            { id: 'item2', component: { ListItem: { content: { literalString: 'Second' } } } },
          ],
        },
      };

      const result = renderer.render(surface);
      expect(result.text).toContain('1. First');
      expect(result.text).toContain('2. Second');
    });
  });

  describe('Form Input Detection', () => {
    it('should detect TextField and require Web App', () => {
      const surface: SurfaceUpdate = {
        surfaceUpdate: {
          surfaceId: 'main',
          components: [
            {
              id: 'input1',
              component: {
                TextField: {
                  label: { literalString: 'Name' },
                  value: { path: '/form/name' },
                },
              },
            },
          ],
        },
      };

      expect(requiresWebApp(surface)).toBe(true);

      const result = renderer.render(surface);
      expect(result.requiresWebApp).toBe(true);
      expect(result.webAppUrl).toContain('session=');
    });

    it('should detect DateTimeInput and require Web App', () => {
      const surface: SurfaceUpdate = {
        surfaceUpdate: {
          surfaceId: 'main',
          components: [
            {
              id: 'date1',
              component: {
                DateTimeInput: {
                  label: { literalString: 'Date' },
                  value: { path: '/form/date' },
                },
              },
            },
          ],
        },
      };

      expect(requiresWebApp(surface)).toBe(true);
    });

    it('should not require Web App for simple components', () => {
      const surface: SurfaceUpdate = {
        surfaceUpdate: {
          surfaceId: 'main',
          components: [
            { id: 't1', component: { Text: { text: { literalString: 'Hello' } } } },
            { id: 'b1', component: { Button: { label: { literalString: 'Click' }, action: { name: 'click' } } } },
          ],
        },
      };

      expect(requiresWebApp(surface)).toBe(false);

      const result = renderer.render(surface);
      expect(result.requiresWebApp).toBeFalsy();
    });
  });

  describe('Data Model Resolution', () => {
    it('should resolve path references from data model', () => {
      const surface: SurfaceUpdate = {
        surfaceUpdate: {
          surfaceId: 'main',
          components: [
            {
              id: 't1',
              component: {
                Text: {
                  text: { path: '/user/name' },
                },
              },
            },
          ],
        },
      };

      const dataModel = {
        user: { name: 'John Doe' },
      };

      const result = renderer.render(surface, dataModel);
      expect(result.text).toContain('John Doe');
    });
  });

  describe('Callback Data', () => {
    it('should serialize and parse action with context', () => {
      const action = {
        name: 'submit',
        context: [
          { key: 'id', value: { literalString: '123' } },
          { key: 'type', value: { literalString: 'form' } },
        ],
      };

      const surface: SurfaceUpdate = {
        surfaceUpdate: {
          surfaceId: 'main',
          components: [
            {
              id: 'btn',
              component: {
                Button: {
                  label: { literalString: 'Submit' },
                  action,
                },
              },
            },
          ],
        },
      };

      const result = renderer.render(surface);
      const callbackData = result.options.reply_markup!.inline_keyboard[0][0].callback_data!;

      const parsed = renderer.parseCallbackData(callbackData);
      expect(parsed.name).toBe('submit');
      expect(parsed.context).toHaveLength(2);
    });
  });

  describe('Divider and Spacer', () => {
    it('should render divider as horizontal line', () => {
      const surface: SurfaceUpdate = {
        surfaceUpdate: {
          surfaceId: 'main',
          components: [{ id: 'd1', component: { Divider: {} } }],
        },
      };

      const result = renderer.render(surface);
      expect(result.text).toContain('───');
    });

    it('should render spacer as newline', () => {
      const surface: SurfaceUpdate = {
        surfaceUpdate: {
          surfaceId: 'main',
          components: [
            { id: 't1', component: { Text: { text: { literalString: 'Before' } } } },
            { id: 's1', component: { Spacer: { height: 16 } } },
            { id: 't2', component: { Text: { text: { literalString: 'After' } } } },
          ],
        },
      };

      const result = renderer.render(surface);
      expect(result.text).toContain('Before');
      expect(result.text).toContain('After');
    });
  });
});

describe('InMemorySessionStore (v0.8 Standard)', () => {
  it('should store and retrieve sessions', () => {
    const store = new InMemorySessionStore();
    const surface: SurfaceUpdate = {
      surfaceUpdate: {
        surfaceId: 'main',
        components: [],
      },
    };

    store.set('session1', surface);
    expect(store.get('session1')).toEqual(surface);
  });

  it('should return undefined for non-existent sessions', () => {
    const store = new InMemorySessionStore();
    expect(store.get('nonexistent')).toBeUndefined();
  });

  it('should delete sessions', () => {
    const store = new InMemorySessionStore();
    const surface: SurfaceUpdate = {
      surfaceUpdate: {
        surfaceId: 'main',
        components: [],
      },
    };

    store.set('session1', surface);
    store.delete('session1');
    expect(store.get('session1')).toBeUndefined();
  });
});
