import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  A2UIStateManager,
  createA2UIStateManager,
  SurfaceState,
  DataModelState,
} from './state.js';
import { SurfaceUpdate, DataModelUpdate, BeginRendering } from './types.js';

describe('A2UIStateManager (v0.8 Standard)', () => {
  let state: A2UIStateManager;

  beforeEach(() => {
    state = new A2UIStateManager();
  });

  describe('Surface Management', () => {
    const surfaceUpdate: SurfaceUpdate = {
      surfaceUpdate: {
        surfaceId: 'main',
        components: [
          {
            id: 'text-1',
            component: { Text: { text: { literalString: 'Hello' } } },
          },
          {
            id: 'btn-1',
            component: {
              Button: {
                label: { literalString: 'Click' },
                action: { name: 'click' },
              },
            },
          },
        ],
      },
    };

    it('should process surface update', () => {
      state.processMessage(surfaceUpdate);

      const surface = state.getSurface('main');
      expect(surface).toBeDefined();
      expect(surface?.surfaceId).toBe('main');
      expect(surface?.components.size).toBe(2);
    });

    it('should maintain component order', () => {
      state.processMessage(surfaceUpdate);

      const surface = state.getSurface('main');
      expect(surface?.order).toEqual(['text-1', 'btn-1']);
    });

    it('should call onSurfaceUpdate event', () => {
      const onSurfaceUpdate = vi.fn();
      state.on('onSurfaceUpdate', onSurfaceUpdate);

      state.processMessage(surfaceUpdate);

      expect(onSurfaceUpdate).toHaveBeenCalledWith('main', expect.any(Object));
    });

    it('should get component by ID', () => {
      state.processMessage(surfaceUpdate);

      const component = state.getComponent('main', 'text-1');
      expect(component).toBeDefined();
      expect(component?.id).toBe('text-1');
    });

    it('should return undefined for missing component', () => {
      state.processMessage(surfaceUpdate);
      expect(state.getComponent('main', 'nonexistent')).toBeUndefined();
    });

    it('should get components in order', () => {
      state.processMessage(surfaceUpdate);

      const components = state.getComponentsInOrder('main');
      expect(components.length).toBe(2);
      expect(components[0].id).toBe('text-1');
      expect(components[1].id).toBe('btn-1');
    });

    it('should return empty array for missing surface', () => {
      expect(state.getComponentsInOrder('nonexistent')).toEqual([]);
    });

    it('should clear a surface', () => {
      state.processMessage(surfaceUpdate);
      state.clearSurface('main');

      expect(state.getSurface('main')).toBeUndefined();
    });

    it('should clear all surfaces', () => {
      state.processMessage(surfaceUpdate);
      state.processMessage({
        surfaceUpdate: {
          surfaceId: 'sidebar',
          components: [],
        },
      });

      state.clearAllSurfaces();

      expect(state.getAllSurfaces().size).toBe(0);
    });

    it('should handle beginRendering message', () => {
      const onBeginRendering = vi.fn();
      state.on('onBeginRendering', onBeginRendering);

      state.processMessage(surfaceUpdate);
      state.processMessage({
        beginRendering: {
          surfaceId: 'main',
          root: 'text-1',
        },
      });

      expect(onBeginRendering).toHaveBeenCalledWith('main', 'text-1');

      const surface = state.getSurface('main');
      expect(surface?.root).toBe('text-1');
    });
  });

  describe('Data Model Management', () => {
    const dataUpdate: DataModelUpdate = {
      dataModelUpdate: {
        surfaceId: 'booking',
        contents: [
          { key: 'date', valueString: '2026-03-15' },
          { key: 'destination', valueString: 'Tokyo' },
        ],
      },
    };

    it('should process data model update', () => {
      state.processMessage(dataUpdate);

      const model = state.getDataModel('booking');
      expect(model).toBeDefined();
      expect(model?.surfaceId).toBe('booking');
      expect(model?.data.date).toBe('2026-03-15');
      expect(model?.data.destination).toBe('Tokyo');
    });

    it('should merge data model updates', () => {
      state.processMessage(dataUpdate);
      state.processMessage({
        dataModelUpdate: {
          surfaceId: 'booking',
          contents: [{ key: 'passengers', valueNumber: 2 }],
        },
      });

      const model = state.getDataModel('booking');
      expect(model?.data.date).toBe('2026-03-15');
      expect(model?.data.passengers).toBe(2);
    });

    it('should call onDataModelUpdate event', () => {
      const onDataModelUpdate = vi.fn();
      state.on('onDataModelUpdate', onDataModelUpdate);

      state.processMessage(dataUpdate);

      expect(onDataModelUpdate).toHaveBeenCalledWith('booking', expect.any(Object));
    });

    it('should get data value by path', () => {
      state.processMessage(dataUpdate);

      expect(state.getDataValue('booking', '/date')).toBe('2026-03-15');
      expect(state.getDataValue('booking', 'destination')).toBe('Tokyo');
    });

    it('should return undefined for missing model', () => {
      expect(state.getDataValue('nonexistent', '/path')).toBeUndefined();
    });

    it('should set data value', () => {
      state.setDataValue('booking', '/date', '2026-04-01');

      const model = state.getDataModel('booking');
      expect(model?.data.date).toBe('2026-04-01');
    });

    it('should create model if not exists when setting value', () => {
      state.setDataValue('newModel', '/key', 'value');

      const model = state.getDataModel('newModel');
      expect(model).toBeDefined();
      expect(model?.data.key).toBe('value');
    });

    it('should set nested data value', () => {
      state.setDataValue('booking', '/user/name', 'John');

      const model = state.getDataModel('booking');
      expect((model?.data.user as any)?.name).toBe('John');
    });

    it('should clear a data model', () => {
      state.processMessage(dataUpdate);
      state.clearDataModel('booking');

      expect(state.getDataModel('booking')).toBeUndefined();
    });

    it('should clear all data models', () => {
      state.processMessage(dataUpdate);
      state.processMessage({
        dataModelUpdate: {
          surfaceId: 'user',
          contents: [{ key: 'name', valueString: 'John' }],
        },
      });

      state.clearAllDataModels();

      expect(state.getAllDataModels().size).toBe(0);
    });
  });

  describe('Value Resolution', () => {
    beforeEach(() => {
      state.processMessage({
        dataModelUpdate: {
          surfaceId: 'booking',
          contents: [
            { key: 'date', valueString: '2026-03-15' },
            {
              key: 'passenger',
              valueMap: [{ key: 'name', valueString: 'John' }],
            },
          ],
        },
      });
      state.processMessage({
        dataModelUpdate: {
          surfaceId: 'user',
          contents: [{ key: 'email', valueString: 'john@example.com' }],
        },
      });
    });

    it('should resolve literal string', () => {
      expect(state.resolveBoundValue({ literalString: 'Hello' })).toBe('Hello');
    });

    it('should resolve path from specific model', () => {
      expect(state.resolveBoundValue({ path: '/booking/date' })).toBe('2026-03-15');
    });

    it('should resolve nested path', () => {
      expect(state.resolveBoundValue({ path: '/booking/passenger/name' })).toBe('John');
    });

    it('should search all models when path not found in specified model', () => {
      expect(state.resolveBoundValue({ path: '/email' })).toBe('john@example.com');
    });

    it('should return empty string for missing path', () => {
      expect(state.resolveBoundValue({ path: '/nonexistent/path' })).toBe('');
    });
  });

  describe('Children Resolution', () => {
    beforeEach(() => {
      state.processMessage({
        surfaceUpdate: {
          surfaceId: 'main',
          components: [
            { id: 'child-1', component: { Text: { text: { literalString: 'A' } } } },
            { id: 'child-2', component: { Text: { text: { literalString: 'B' } } } },
            { id: 'child-3', component: { Text: { text: { literalString: 'C' } } } },
          ],
        },
      });
    });

    it('should resolve explicit list children', () => {
      const children = state.resolveChildren(
        { explicitList: ['child-1', 'child-3'] },
        'main'
      );

      expect(children.length).toBe(2);
      expect(children[0].id).toBe('child-1');
      expect(children[1].id).toBe('child-3');
    });

    it('should filter out missing children', () => {
      const children = state.resolveChildren(
        { explicitList: ['child-1', 'nonexistent', 'child-2'] },
        'main'
      );

      expect(children.length).toBe(2);
    });

    it('should return empty array for missing surface', () => {
      const children = state.resolveChildren(
        { explicitList: ['child-1'] },
        'nonexistent'
      );

      expect(children).toEqual([]);
    });
  });

  describe('Multiple Message Processing', () => {
    it('should process multiple messages', () => {
      state.processMessages([
        {
          surfaceUpdate: {
            surfaceId: 'main',
            components: [
              { id: 'text-1', component: { Text: { text: { literalString: 'Hi' } } } },
            ],
          },
        },
        {
          dataModelUpdate: {
            surfaceId: 'form',
            contents: [{ key: 'name', valueString: 'John' }],
          },
        },
        {
          beginRendering: {
            surfaceId: 'main',
          },
        },
      ]);

      expect(state.getSurface('main')).toBeDefined();
      expect(state.getDataModel('form')).toBeDefined();
    });
  });

  describe('Reset', () => {
    it('should clear all state', () => {
      state.processMessage({
        surfaceUpdate: {
          surfaceId: 'main',
          components: [],
        },
      });
      state.processMessage({
        dataModelUpdate: {
          surfaceId: 'booking',
          contents: [],
        },
      });

      state.reset();

      expect(state.getAllSurfaces().size).toBe(0);
      expect(state.getAllDataModels().size).toBe(0);
    });
  });

  describe('Factory Function', () => {
    it('should create A2UIStateManager instance', () => {
      const manager = createA2UIStateManager();
      expect(manager).toBeInstanceOf(A2UIStateManager);
    });
  });
});
