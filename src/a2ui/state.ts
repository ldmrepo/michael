/**
 * A2UI State Manager (v0.8 Standard)
 *
 * Manages Surface and DataModel state for A2UI rendering.
 * Handles surface updates, data model changes, and value resolution.
 *
 * @see https://a2ui.org/specification/v0.8-a2ui/
 */

import {
  A2UIMessage,
  SurfaceUpdate,
  DataModelUpdate,
  DeleteSurface,
  ComponentDefinition,
  BoundValue,
  DataModelContent,
  resolveBoundValue,
  isSurfaceUpdate,
  isDataModelUpdate,
  isBeginRendering,
  isDeleteSurface,
  ExplicitList,
  PathReference,
} from './types.js';

// --- Surface State ---

/**
 * Surface state containing components
 */
export interface SurfaceState {
  /** Surface ID */
  surfaceId: string;
  /** Component definitions keyed by ID */
  components: Map<string, ComponentDefinition>;
  /** Component order (IDs in order of definition) */
  order: string[];
  /** Root component ID for rendering */
  root?: string;
  /** Last update timestamp */
  lastUpdated: number;
}

// --- Data Model State ---

/**
 * Data model state
 */
export interface DataModelState {
  /** Surface ID (v0.8 uses surfaceId instead of modelId) */
  surfaceId: string;
  /** Model data (extracted from contents) */
  data: Record<string, unknown>;
  /** Last update timestamp */
  lastUpdated: number;
}

// --- State Manager Events ---

export interface A2UIStateEvents {
  onSurfaceUpdate?: (surfaceId: string, state: SurfaceState) => void;
  onDataModelUpdate?: (surfaceId: string, state: DataModelState) => void;
  onBeginRendering?: (surfaceId: string, root?: string) => void;
  onDeleteSurface?: (surfaceId: string) => void;
}

// --- A2UI State Manager ---

/**
 * A2UI State Manager (v0.8 Standard)
 *
 * Manages the state of A2UI surfaces and data models.
 *
 * @example
 * ```ts
 * const state = new A2UIStateManager();
 *
 * state.on('onSurfaceUpdate', (surfaceId, surface) => {
 *   renderSurface(surface);
 * });
 *
 * state.processMessage({
 *   surfaceUpdate: {
 *     surfaceId: 'main',
 *     components: [...]
 *   }
 * });
 * ```
 */
export class A2UIStateManager {
  private surfaces: Map<string, SurfaceState> = new Map();
  private dataModels: Map<string, DataModelState> = new Map();
  private events: A2UIStateEvents = {};

  /**
   * Register event handlers
   */
  on<K extends keyof A2UIStateEvents>(event: K, handler: A2UIStateEvents[K]): void {
    this.events[event] = handler;
  }

  /**
   * Process an A2UI message and update state (v0.8 standard)
   */
  processMessage(message: A2UIMessage): void {
    if (isSurfaceUpdate(message)) {
      this.handleSurfaceUpdate(message);
    } else if (isDataModelUpdate(message)) {
      this.handleDataModelUpdate(message);
    } else if (isBeginRendering(message)) {
      const { surfaceId, root } = message.beginRendering;
      this.handleBeginRendering(surfaceId, root);
    } else if (isDeleteSurface(message)) {
      this.handleDeleteSurface(message);
    }
  }

  /**
   * Process multiple A2UI messages
   */
  processMessages(messages: A2UIMessage[]): void {
    for (const message of messages) {
      this.processMessage(message);
    }
  }

  // --- Surface Management ---

  /**
   * Handle surface update message (v0.8 standard)
   */
  private handleSurfaceUpdate(update: SurfaceUpdate): void {
    const { surfaceId, components: componentList } = update.surfaceUpdate;
    const components = new Map<string, ComponentDefinition>();
    const order: string[] = [];

    for (const component of componentList) {
      components.set(component.id, component);
      order.push(component.id);
    }

    const state: SurfaceState = {
      surfaceId,
      components,
      order,
      lastUpdated: Date.now(),
    };

    this.surfaces.set(surfaceId, state);
    this.events.onSurfaceUpdate?.(surfaceId, state);
  }

  /**
   * Handle begin rendering message
   */
  private handleBeginRendering(surfaceId: string, root?: string): void {
    const surface = this.surfaces.get(surfaceId);
    if (surface) {
      surface.root = root;
    }
    this.events.onBeginRendering?.(surfaceId, root);
  }

  /**
   * Handle delete surface message (v0.8 standard)
   */
  private handleDeleteSurface(message: DeleteSurface): void {
    const { surfaceId } = message.deleteSurface;
    this.surfaces.delete(surfaceId);
    this.dataModels.delete(surfaceId);
    this.events.onDeleteSurface?.(surfaceId);
  }

  /**
   * Get a surface state
   */
  getSurface(surfaceId: string): SurfaceState | undefined {
    return this.surfaces.get(surfaceId);
  }

  /**
   * Get all surfaces
   */
  getAllSurfaces(): Map<string, SurfaceState> {
    return new Map(this.surfaces);
  }

  /**
   * Get a component from a surface
   */
  getComponent(surfaceId: string, componentId: string): ComponentDefinition | undefined {
    return this.surfaces.get(surfaceId)?.components.get(componentId);
  }

  /**
   * Get components in order from a surface
   */
  getComponentsInOrder(surfaceId: string): ComponentDefinition[] {
    const surface = this.surfaces.get(surfaceId);
    if (!surface) return [];

    return surface.order
      .map((id) => surface.components.get(id))
      .filter((c): c is ComponentDefinition => c !== undefined);
  }

  /**
   * Clear a surface
   */
  clearSurface(surfaceId: string): void {
    this.surfaces.delete(surfaceId);
  }

  /**
   * Clear all surfaces
   */
  clearAllSurfaces(): void {
    this.surfaces.clear();
  }

  // --- Data Model Management ---

  /**
   * Handle data model update message (v0.8 standard)
   */
  private handleDataModelUpdate(update: DataModelUpdate): void {
    const { surfaceId, contents } = update.dataModelUpdate;
    const existing = this.dataModels.get(surfaceId);

    // Convert contents to data object
    const newData = this.contentsToData(contents);
    const mergedData = existing ? { ...existing.data, ...newData } : newData;

    const state: DataModelState = {
      surfaceId,
      data: mergedData,
      lastUpdated: Date.now(),
    };

    this.dataModels.set(surfaceId, state);
    this.events.onDataModelUpdate?.(surfaceId, state);
  }

  /**
   * Convert DataModelContent array to data object
   */
  private contentsToData(contents: DataModelContent[]): Record<string, unknown> {
    const result: Record<string, unknown> = {};

    for (const content of contents) {
      if (content.valueString !== undefined) {
        result[content.key] = content.valueString;
      } else if (content.valueNumber !== undefined) {
        result[content.key] = content.valueNumber;
      } else if (content.valueBoolean !== undefined) {
        result[content.key] = content.valueBoolean;
      } else if (content.valueMap !== undefined) {
        result[content.key] = this.contentsToData(content.valueMap);
      } else if (content.valueList !== undefined) {
        result[content.key] = this.valueListToArray(content.valueList);
      }
    }

    return result;
  }

  /**
   * Convert valueList to array
   */
  private valueListToArray(valueList: Array<{
    valueString?: string;
    valueNumber?: number;
    valueBoolean?: boolean;
    valueMap?: DataModelContent[];
    valueList?: unknown[];
  }>): unknown[] {
    return valueList.map((item) => {
      if (item.valueString !== undefined) return item.valueString;
      if (item.valueNumber !== undefined) return item.valueNumber;
      if (item.valueBoolean !== undefined) return item.valueBoolean;
      if (item.valueMap !== undefined) return this.contentsToData(item.valueMap);
      if (item.valueList !== undefined) return this.valueListToArray(item.valueList as typeof valueList);
      return null;
    });
  }

  /**
   * Get a data model state
   */
  getDataModel(surfaceId: string): DataModelState | undefined {
    return this.dataModels.get(surfaceId);
  }

  /**
   * Get data model value by path
   */
  getDataValue(surfaceId: string, path: string): unknown {
    const model = this.dataModels.get(surfaceId);
    if (!model) return undefined;

    return resolveBoundValue({ path }, model.data);
  }

  /**
   * Set a value in a data model
   */
  setDataValue(surfaceId: string, path: string, value: unknown): void {
    let model = this.dataModels.get(surfaceId);

    if (!model) {
      model = {
        surfaceId,
        data: {},
        lastUpdated: Date.now(),
      };
      this.dataModels.set(surfaceId, model);
    }

    // Simple path setting (supports /foo/bar format)
    const cleanPath = path.startsWith('/') ? path.slice(1) : path;
    const parts = cleanPath.split('/');

    let current = model.data;
    for (let i = 0; i < parts.length - 1; i++) {
      const part = parts[i];
      if (!(part in current) || typeof current[part] !== 'object') {
        current[part] = {};
      }
      current = current[part] as Record<string, unknown>;
    }

    current[parts[parts.length - 1]] = value;
    model.lastUpdated = Date.now();

    this.events.onDataModelUpdate?.(surfaceId, model);
  }

  /**
   * Get all data models
   */
  getAllDataModels(): Map<string, DataModelState> {
    return new Map(this.dataModels);
  }

  /**
   * Clear a data model
   */
  clearDataModel(surfaceId: string): void {
    this.dataModels.delete(surfaceId);
  }

  /**
   * Clear all data models
   */
  clearAllDataModels(): void {
    this.dataModels.clear();
  }

  // --- Value Resolution ---

  /**
   * Resolve a BoundValue using all data models
   *
   * If the path starts with a surface ID (e.g., /booking/date),
   * it will look up the value from that specific model.
   * Otherwise, it searches all models.
   */
  resolveBoundValue(value: BoundValue): string {
    if (value.literalString !== undefined) {
      return value.literalString;
    }

    if (value.literalNumber !== undefined) {
      return String(value.literalNumber);
    }

    if (value.literalBoolean !== undefined) {
      return String(value.literalBoolean);
    }

    if (value.path === undefined) {
      return '';
    }

    const path = value.path;
    const cleanPath = path.startsWith('/') ? path.slice(1) : path;
    const parts = cleanPath.split('/');

    // First part might be surface ID
    const possibleSurfaceId = parts[0];
    const model = this.dataModels.get(possibleSurfaceId);

    if (model) {
      // Try to resolve from the specific model
      const remainingPath = parts.slice(1).join('/');
      const result = resolveBoundValue({ path: remainingPath }, model.data);
      if (result !== '') return String(result);
    }

    // Try all models
    for (const [, modelState] of this.dataModels) {
      const result = resolveBoundValue(value, modelState.data);
      if (result !== '') return String(result);
    }

    return '';
  }

  /**
   * Resolve children list (ExplicitList or PathReference)
   */
  resolveChildren(
    children: ExplicitList | PathReference,
    surfaceId: string
  ): ComponentDefinition[] {
    if ('explicitList' in children) {
      const surface = this.surfaces.get(surfaceId);
      if (!surface) return [];

      return children.explicitList
        .map((id) => surface.components.get(id))
        .filter((c): c is ComponentDefinition => c !== undefined);
    }

    // PathReference - resolve from data model
    const ids = this.resolveBoundValue(children);
    if (!ids) return [];

    // Assume IDs are comma-separated if from data model
    const idList = ids.split(',').map((s) => s.trim());
    const surface = this.surfaces.get(surfaceId);
    if (!surface) return [];

    return idList
      .map((id) => surface.components.get(id))
      .filter((c): c is ComponentDefinition => c !== undefined);
  }

  // --- Reset ---

  /**
   * Clear all state
   */
  reset(): void {
    this.surfaces.clear();
    this.dataModels.clear();
  }
}

// --- Factory Function ---

/**
 * Create an A2UI state manager
 */
export function createA2UIStateManager(): A2UIStateManager {
  return new A2UIStateManager();
}
