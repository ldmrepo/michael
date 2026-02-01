/**
 * A2UI v0.8 Utility Functions
 * https://a2ui.org/specification/v0.8-a2ui/
 */

import { BoundValue, Surface, A2UIMessage, A2UIComponent } from './types';

/**
 * Resolve a BoundValue to its final value
 *
 * Resolution order:
 * 1. If path exists, look up value in dataModel
 * 2. Fall back to literal values (string, number, boolean)
 *
 * @see https://a2ui.org/specification/v0.8-a2ui/#boundvalue-resolution
 */
export function resolveBoundValue(
    value: BoundValue | string | number | boolean | undefined,
    dataModel: Map<string, any>
): string | number | boolean {
    if (value === undefined || value === null) return '';
    if (typeof value === 'string') return value;
    if (typeof value === 'number') return value;
    if (typeof value === 'boolean') return value;

    // Path reference - look up in data model
    if (value.path) {
        const resolved = getNestedValue(dataModel, value.path);
        if (resolved !== undefined) return resolved;
    }

    // Literal fallback (check in order: string, number, boolean)
    if (value.literalString !== undefined) return value.literalString;
    if (value.literalNumber !== undefined) return value.literalNumber;
    if (value.literalBoolean !== undefined) return value.literalBoolean;

    return '';
}

/**
 * Get nested value from data model using path
 * Supports both JSON Pointer format (/user/name) and dot notation (user.name)
 * @see https://datatracker.ietf.org/doc/html/rfc6901
 */
export function getNestedValue(dataModel: Map<string, any>, path: string): any {
    if (!path) return undefined;

    // Normalize path: support both JSON Pointer (/user/name) and dot notation (user.name)
    let normalizedPath = path;
    if (path.startsWith('/')) {
        // JSON Pointer format: /user/name -> user.name
        normalizedPath = path.slice(1).replace(/\//g, '.');
    }

    const parts = normalizedPath.split('.');
    let current: any = dataModel.get(parts[0]);

    for (let i = 1; i < parts.length && current !== undefined; i++) {
        // Handle array index in JSON Pointer (e.g., /items/0)
        const part = parts[i];
        if (Array.isArray(current) && /^\d+$/.test(part)) {
            current = current[parseInt(part, 10)];
        } else {
            current = current[part];
        }
    }

    return current;
}

/**
 * Create an empty surface
 */
export function createEmptySurface(surfaceId: string = 'main'): Surface {
    return {
        surfaceId,
        components: new Map(),
        dataModel: new Map(),
        rootId: null,
        isReady: false,
    };
}

/**
 * Handle A2UI message and update surface state
 *
 * Message handling order (recommended):
 * 1. surfaceUpdate - add/update components
 * 2. dataModelUpdate - update data model
 * 3. beginRendering - trigger rendering
 *
 * @see https://a2ui.org/specification/v0.8-a2ui/#message-handling
 */
export function handleA2UIMessage(message: A2UIMessage, surface: Surface): Surface {
    const newSurface = { ...surface };

    // Handle surfaceUpdate
    if ('surfaceUpdate' in message) {
        const { components } = message.surfaceUpdate;
        const newComponents = new Map(surface.components);

        for (const comp of components) {
            // Upsert: same id = update, new id = add
            newComponents.set(comp.id, comp);
        }

        newSurface.components = newComponents;
    }

    // Handle dataModelUpdate
    if ('dataModelUpdate' in message) {
        const { contents } = message.dataModelUpdate;
        const newDataModel = new Map(surface.dataModel);

        for (const item of contents) {
            const value = extractTypedValue(item);
            if (value !== undefined) {
                newDataModel.set(item.key, value);
            }
        }

        newSurface.dataModel = newDataModel;
    }

    // Handle beginRendering - trigger render
    if ('beginRendering' in message) {
        newSurface.rootId = message.beginRendering.root;
        newSurface.isReady = true;
    }

    // Handle deleteSurface
    if ('deleteSurface' in message) {
        newSurface.components = new Map();
        newSurface.dataModel = new Map();
        newSurface.rootId = null;
        newSurface.isReady = false;
    }

    return newSurface;
}

/**
 * Extract typed value from dataModelUpdate content item
 */
function extractTypedValue(item: {
    valueString?: string;
    valueNumber?: number;
    valueBoolean?: boolean;
    valueMap?: Record<string, any>;
    valueList?: any[];
}): any {
    if (item.valueString !== undefined) return item.valueString;
    if (item.valueNumber !== undefined) return item.valueNumber;
    if (item.valueBoolean !== undefined) return item.valueBoolean;
    if (item.valueMap !== undefined) return item.valueMap;
    if (item.valueList !== undefined) return item.valueList;
    return undefined;
}

/**
 * Get component type from A2UI component
 */
export function getComponentType(component: A2UIComponent): string {
    return Object.keys(component.component)[0];
}

/**
 * Get component props from A2UI component
 */
export function getComponentProps<T = Record<string, any>>(component: A2UIComponent): T {
    const type = getComponentType(component);
    return component.component[type] as T;
}

/**
 * Children structure with template support
 */
export interface ChildrenDef {
    explicitList?: string[];
    template?: {
        dataPath: string;
        componentId: string;
    };
}

/**
 * Get children IDs from component props (explicit list only)
 */
export function getChildrenIds(children: ChildrenDef | undefined): string[] {
    if (!children) return [];
    return children.explicitList || [];
}

/**
 * Check if children uses template rendering
 */
export function hasTemplateChildren(children: ChildrenDef | undefined): boolean {
    return !!children?.template;
}

/**
 * Get template data for dynamic list rendering
 * Returns array of data items to render with the template component
 */
export function getTemplateData(
    children: ChildrenDef | undefined,
    dataModel: Map<string, any>
): { items: any[]; componentId: string } | null {
    if (!children?.template) return null;

    const { dataPath, componentId } = children.template;
    const items = getNestedValue(dataModel, dataPath);

    if (!Array.isArray(items)) return null;

    return { items, componentId };
}

/**
 * Send userAction to server
 */
export async function sendUserAction(
    actionName: string,
    surfaceId: string,
    componentId: string,
    context: Record<string, any>,
    endpoint: string = '/api/action'
): Promise<void> {
    try {
        await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: actionName,
                surfaceId,
                sourceComponentId: componentId,
                timestamp: new Date().toISOString(),
                context,
            }),
        });
    } catch (error) {
        console.error('Failed to send userAction:', error);
    }
}

/**
 * Resolve action context values
 */
export function resolveActionContext(
    context: Array<{ key: string; value: BoundValue }> | undefined,
    dataModel: Map<string, any>
): Record<string, any> {
    if (!context) return {};

    const resolved: Record<string, any> = {};
    for (const item of context) {
        resolved[item.key] = resolveBoundValue(item.value, dataModel);
    }
    return resolved;
}
