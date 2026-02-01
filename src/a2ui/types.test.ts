import { describe, it, expect } from 'vitest';
import {
  // BoundValue types and functions
  BoundValue,
  LiteralString,
  PathReference,
  isLiteralString,
  isPathReference,
  resolveBoundValue,
  // Message types and guards
  A2UIMessage,
  SurfaceUpdate,
  BeginRendering,
  DataModelUpdate,
  isSurfaceUpdate,
  isBeginRendering,
  isDataModelUpdate,
  // Component types and guards
  A2UIComponentType,
  ComponentDefinition,
  isTextComponent,
  isButtonComponent,
  isImageComponent,
  isCardComponent,
  isRowComponent,
  isColumnComponent,
  isListComponent,
  isTextFieldComponent,
  isDateTimeInputComponent,
  isFormInputComponent,
  getComponentTypeName,
} from './types.js';

describe('A2UI Types', () => {
  describe('BoundValue', () => {
    describe('isLiteralString', () => {
      it('should return true for literal strings', () => {
        const value: BoundValue = { literalString: 'Hello' };
        expect(isLiteralString(value)).toBe(true);
      });

      it('should return false for path references', () => {
        const value: BoundValue = { path: '/foo/bar' };
        expect(isLiteralString(value)).toBe(false);
      });
    });

    describe('isPathReference', () => {
      it('should return true for path references', () => {
        const value: BoundValue = { path: '/foo/bar' };
        expect(isPathReference(value)).toBe(true);
      });

      it('should return false for literal strings', () => {
        const value: BoundValue = { literalString: 'Hello' };
        expect(isPathReference(value)).toBe(false);
      });
    });

    describe('resolveBoundValue', () => {
      it('should resolve literal strings directly', () => {
        const value: BoundValue = { literalString: 'Hello World' };
        expect(resolveBoundValue(value)).toBe('Hello World');
      });

      it('should resolve path references from data model', () => {
        const value: BoundValue = { path: '/user/name' };
        const dataModel = { user: { name: 'John' } };
        expect(resolveBoundValue(value, dataModel)).toBe('John');
      });

      it('should handle leading slash in path', () => {
        const value: BoundValue = { path: '/booking/date' };
        const dataModel = { booking: { date: '2026-03-15' } };
        expect(resolveBoundValue(value, dataModel)).toBe('2026-03-15');
      });

      it('should handle path without leading slash', () => {
        const value: BoundValue = { path: 'booking/date' };
        const dataModel = { booking: { date: '2026-03-15' } };
        expect(resolveBoundValue(value, dataModel)).toBe('2026-03-15');
      });

      it('should return empty string for missing path', () => {
        const value: BoundValue = { path: '/user/email' };
        const dataModel = { user: { name: 'John' } };
        expect(resolveBoundValue(value, dataModel)).toBe('');
      });

      it('should return empty string when no data model provided', () => {
        const value: BoundValue = { path: '/user/name' };
        expect(resolveBoundValue(value)).toBe('');
      });

      it('should convert non-string values to number', () => {
        const value: BoundValue = { path: '/count' };
        const dataModel = { count: 42 };
        expect(resolveBoundValue(value, dataModel)).toBe(42);
      });
    });
  });

  describe('A2UI Messages (v0.8 Standard)', () => {
    describe('isSurfaceUpdate', () => {
      it('should identify SurfaceUpdate messages', () => {
        const msg: A2UIMessage = {
          surfaceUpdate: {
            surfaceId: 'main',
            components: [],
          },
        };
        expect(isSurfaceUpdate(msg)).toBe(true);
        expect(isBeginRendering(msg)).toBe(false);
        expect(isDataModelUpdate(msg)).toBe(false);
      });
    });

    describe('isBeginRendering', () => {
      it('should identify BeginRendering messages', () => {
        const msg: A2UIMessage = {
          beginRendering: {
            surfaceId: 'main',
          },
        };
        expect(isBeginRendering(msg)).toBe(true);
        expect(isSurfaceUpdate(msg)).toBe(false);
      });
    });

    describe('isDataModelUpdate', () => {
      it('should identify DataModelUpdate messages', () => {
        const msg: A2UIMessage = {
          dataModelUpdate: {
            surfaceId: 'booking',
            contents: [{ key: 'date', valueString: '2026-03-15' }],
          },
        };
        expect(isDataModelUpdate(msg)).toBe(true);
        expect(isSurfaceUpdate(msg)).toBe(false);
      });
    });
  });

  describe('Component Type Guards', () => {
    it('should identify Text component', () => {
      const comp: A2UIComponentType = {
        Text: { text: { literalString: 'Hello' } },
      };
      expect(isTextComponent(comp)).toBe(true);
      expect(isButtonComponent(comp)).toBe(false);
    });

    it('should identify Button component', () => {
      const comp: A2UIComponentType = {
        Button: {
          label: { literalString: 'Click' },
          action: { name: 'submit' },
        },
      };
      expect(isButtonComponent(comp)).toBe(true);
      expect(isTextComponent(comp)).toBe(false);
    });

    it('should identify Image component', () => {
      const comp: A2UIComponentType = {
        Image: { src: { literalString: 'https://example.com/image.png' } },
      };
      expect(isImageComponent(comp)).toBe(true);
    });

    it('should identify Card component', () => {
      const comp: A2UIComponentType = {
        Card: {
          title: { literalString: 'Card Title' },
          children: { explicitList: ['child1', 'child2'] },
        },
      };
      expect(isCardComponent(comp)).toBe(true);
    });

    it('should identify Row component', () => {
      const comp: A2UIComponentType = {
        Row: { children: { explicitList: [] } },
      };
      expect(isRowComponent(comp)).toBe(true);
    });

    it('should identify Column component', () => {
      const comp: A2UIComponentType = {
        Column: { children: { explicitList: [] } },
      };
      expect(isColumnComponent(comp)).toBe(true);
    });

    it('should identify List component', () => {
      const comp: A2UIComponentType = {
        List: { children: { explicitList: [] } },
      };
      expect(isListComponent(comp)).toBe(true);
    });

    it('should identify TextField component', () => {
      const comp: A2UIComponentType = {
        TextField: {
          label: { literalString: 'Name' },
          value: { path: '/form/name' },
        },
      };
      expect(isTextFieldComponent(comp)).toBe(true);
    });

    it('should identify DateTimeInput component', () => {
      const comp: A2UIComponentType = {
        DateTimeInput: {
          label: { literalString: 'Date' },
          value: { path: '/form/date' },
        },
      };
      expect(isDateTimeInputComponent(comp)).toBe(true);
    });
  });

  describe('isFormInputComponent', () => {
    it('should return true for TextField', () => {
      const comp: A2UIComponentType = {
        TextField: {
          label: { literalString: 'Name' },
          value: { path: '/name' },
        },
      };
      expect(isFormInputComponent(comp)).toBe(true);
    });

    it('should return true for DateTimeInput', () => {
      const comp: A2UIComponentType = {
        DateTimeInput: {
          label: { literalString: 'Date' },
          value: { path: '/date' },
        },
      };
      expect(isFormInputComponent(comp)).toBe(true);
    });

    it('should return false for Text', () => {
      const comp: A2UIComponentType = {
        Text: { text: { literalString: 'Hello' } },
      };
      expect(isFormInputComponent(comp)).toBe(false);
    });

    it('should return false for Button', () => {
      const comp: A2UIComponentType = {
        Button: {
          label: { literalString: 'Click' },
          action: { name: 'click' },
        },
      };
      expect(isFormInputComponent(comp)).toBe(false);
    });
  });

  describe('getComponentTypeName', () => {
    it('should return correct type names', () => {
      expect(getComponentTypeName({ Text: { text: { literalString: '' } } })).toBe('Text');
      expect(getComponentTypeName({ Button: { label: { literalString: '' }, action: { name: '' } } })).toBe('Button');
      expect(getComponentTypeName({ Image: { src: { literalString: '' } } })).toBe('Image');
      expect(getComponentTypeName({ Card: { title: { literalString: '' }, children: { explicitList: [] } } })).toBe('Card');
      expect(getComponentTypeName({ Row: { children: { explicitList: [] } } })).toBe('Row');
      expect(getComponentTypeName({ Column: { children: { explicitList: [] } } })).toBe('Column');
      expect(getComponentTypeName({ Divider: {} })).toBe('Divider');
      expect(getComponentTypeName({ Spacer: { height: 10 } })).toBe('Spacer');
    });
  });

  describe('ComponentDefinition', () => {
    it('should have correct structure', () => {
      const def: ComponentDefinition = {
        id: 'text-1',
        component: {
          Text: { text: { literalString: 'Hello' }, usageHint: 'h1' },
        },
      };

      expect(def.id).toBe('text-1');
      expect(isTextComponent(def.component)).toBe(true);
    });
  });

  describe('SurfaceUpdate Structure', () => {
    it('should support complete surface definition', () => {
      const surface: SurfaceUpdate = {
        type: 'surfaceUpdate',
        surfaceId: 'main',
        components: [
          {
            id: 'header',
            component: {
              Text: { text: { literalString: 'Welcome' }, usageHint: 'h1' },
            },
          },
          {
            id: 'submit-btn',
            component: {
              Button: {
                label: { literalString: 'Submit' },
                action: {
                  name: 'submit_form',
                  context: [
                    { key: 'date', value: { path: '/form/date' } },
                  ],
                },
                variant: 'primary',
              },
            },
          },
          {
            id: 'name-field',
            component: {
              TextField: {
                label: { literalString: 'Your Name' },
                value: { path: '/form/name' },
                placeholder: { literalString: 'Enter your name' },
                required: true,
              },
            },
          },
        ],
      };

      expect(surface.components.length).toBe(3);
      expect(isTextComponent(surface.components[0].component)).toBe(true);
      expect(isButtonComponent(surface.components[1].component)).toBe(true);
      expect(isTextFieldComponent(surface.components[2].component)).toBe(true);
    });
  });
});
