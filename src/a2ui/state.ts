/**
 * A2UI State Manager
 *
 * Manages Surface and DataModel state for A2UI rendering.
 * Handles surface updates, data model changes, and value resolution.
 */

import {
  A2UIMessage,
  SurfaceUpdate,
  DataModelUpdate,
  ComponentDefinition,
  BoundValue,
  resolveBoundValue,
  isSurfaceUpdate,
  isDataModelUpdate,
  isBeginRendering,
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
  /** Model ID */
  modelId: string;
  /** Model data */
  data: Record<string, unknown>;
  /** Last update timestamp */
  lastUpdated: number;
}

// --- State Manager Events ---

export interface A2UIStateEvents {
  onSurfaceUpdate?: (surfaceId: string, state: SurfaceState) => void;
  onDataModelUpdate?: (modelId: string, state: DataModelState) => void;
  onBeginRendering?: (surfaceId: string, root?: string) => void;
}

// --- A2UI State Manager ---

/**
 * A2UI State Manager
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
 *   type: 'surfaceUpdate',
 *   surfaceId: 'main',
 *   components: [...]
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
   * Process an A2UI message and update state
   */
  processMessage(message: A2UIMessage): void {
    if (isSurfaceUpdate(message)) {
      this.handleSurfaceUpdate(message);
    } else if (isDataModelUpdate(message)) {
      this.handleDataModelUpdate(message);
    } else if (isBeginRendering(message)) {
      this.handleBeginRendering(message.surfaceId, message.root);
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
   * Handle surface update message
   */
  private handleSurfaceUpdate(update: SurfaceUpdate): void {
    const components = new Map<string, ComponentDefinition>();
    const order: string[] = [];

    for (const component of update.components) {
      components.set(component.id, component);
      order.push(component.id);
    }

    const state: SurfaceState = {
      surfaceId: update.surfaceId,
      components,
      order,
      lastUpdated: Date.now(),
    };

    this.surfaces.set(update.surfaceId, state);
    this.events.onSurfaceUpdate?.(update.surfaceId, state);
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
   * Handle data model update message
   */
  private handleDataModelUpdate(update: DataModelUpdate): void {
    const existing = this.dataModels.get(update.modelId);
    const mergedData = existing
      ? { ...existing.data, ...update.data }
      : update.data;

    const state: DataModelState = {
      modelId: update.modelId,
      data: mergedData,
      lastUpdated: Date.now(),
    };

    this.dataModels.set(update.modelId, state);
    this.events.onDataModelUpdate?.(update.modelId, state);
  }

  /**
   * Get a data model state
   */
  getDataModel(modelId: string): DataModelState | undefined {
    return this.dataModels.get(modelId);
  }

  /**
   * Get data model value by path
   */
  getDataValue(modelId: string, path: string): unknown {
    const model = this.dataModels.get(modelId);
    if (!model) return undefined;

    return resolveBoundValue({ path }, model.data);
  }

  /**
   * Set a value in a data model
   */
  setDataValue(modelId: string, path: string, value: unknown): void {
    let model = this.dataModels.get(modelId);

    if (!model) {
      model = {
        modelId,
        data: {},
        lastUpdated: Date.now(),
      };
      this.dataModels.set(modelId, model);
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

    this.events.onDataModelUpdate?.(modelId, model);
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
  clearDataModel(modelId: string): void {
    this.dataModels.delete(modelId);
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
   * If the path starts with a model ID (e.g., /booking/date),
   * it will look up the value from that specific model.
   * Otherwise, it searches all models.
   */
  resolveBoundValue(value: BoundValue): string {
    if ('literalString' in value) {
      return value.literalString;
    }

    const path = value.path;
    const cleanPath = path.startsWith('/') ? path.slice(1) : path;
    const parts = cleanPath.split('/');

    // First part might be model ID
    const possibleModelId = parts[0];
    const model = this.dataModels.get(possibleModelId);

    if (model) {
      // Try to resolve from the specific model
      const remainingPath = parts.slice(1).join('/');
      const result = resolveBoundValue({ path: remainingPath }, model.data);
      if (result) return result;
    }

    // Try all models
    for (const [, modelState] of this.dataModels) {
      const result = resolveBoundValue(value, modelState.data);
      if (result) return result;
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
