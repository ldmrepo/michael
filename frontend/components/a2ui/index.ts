/**
 * A2UI v0.8 React Renderer
 *
 * Standard-compliant A2UI renderer for React applications.
 *
 * @see https://a2ui.org/specification/v0.8-a2ui/
 * @see https://a2ui.org/guides/renderer-development/
 *
 * Usage:
 * ```tsx
 * import { A2UIRenderer, createEmptySurface, handleA2UIMessage } from '@/components/a2ui';
 *
 * // Create surface
 * const surface = createEmptySurface('main');
 *
 * // Handle incoming A2UI messages
 * const newSurface = handleA2UIMessage(message, surface);
 *
 * // Render
 * <A2UIRenderer surface={surface} />
 * ```
 */

// Main renderer
export { A2UIRenderer, default } from './A2UIRenderer';

// Types
export type {
    // Core types
    BoundValue,
    Children,
    Action,
    A2UIComponent,
    Surface,
    RendererProps,

    // Component props
    TextProps,
    ImageProps,
    ButtonProps,
    CardProps,
    RowProps,
    ColumnProps,
    ListProps,
    ListItemProps,

    // Messages
    A2UIMessage,
    SurfaceUpdate,
    DataModelUpdate,
    BeginRendering,
    DeleteSurface,
    UserAction,

    // Constants
    StandardComponentType,
} from './types';

export { STANDARD_CATALOG_ID, STANDARD_COMPONENT_TYPES } from './types';

// Utilities
export {
    // BoundValue resolution
    resolveBoundValue,
    getNestedValue,

    // Surface management
    createEmptySurface,
    handleA2UIMessage,

    // Component helpers
    getComponentType,
    getComponentProps,
    getChildrenIds,

    // User action
    sendUserAction,
    resolveActionContext,
} from './utils';

// Individual renderers (for custom composition)
export {
    TextRenderer,
    ImageRenderer,
    ButtonRenderer,
    CardRenderer,
    RowRenderer,
    ColumnRenderer,
    ListRenderer,
    ListItemRenderer,
    // Action handler for AG-UI integration
    setActionHandler,
    clearActionHandler,
} from './renderers';
