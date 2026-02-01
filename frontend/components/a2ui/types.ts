/**
 * A2UI v0.8 Type Definitions
 * https://a2ui.org/specification/v0.8-a2ui/
 */

// --- BoundValue ---

/**
 * BoundValue: literal value or data model path reference
 * @see https://a2ui.org/specification/v0.8-a2ui/#boundvalue
 */
export interface BoundValue {
    literalString?: string;
    literalNumber?: number;
    literalBoolean?: boolean;
    path?: string;
}

// --- Children ---

/**
 * Children definition for container components
 * @see https://a2ui.org/specification/v0.8-a2ui/#children
 */
export interface Children {
    explicitList?: string[];
    template?: {
        dataPath: string;
        componentId: string;
    };
}

// --- Action ---

/**
 * Action definition for interactive components
 * @see https://a2ui.org/specification/v0.8-a2ui/#action
 */
export interface Action {
    name: string;
    context?: Array<{
        key: string;
        value: BoundValue;
    }>;
}

// --- Component Wrapper ---

/**
 * A2UI Component wrapper structure
 * Each component has exactly one type key
 */
export interface A2UIComponent {
    id: string;
    component: {
        [componentType: string]: Record<string, any>;
    };
}

// --- Standard Component Props ---

export interface TextProps {
    text: BoundValue;
    usageHint?: 'h1' | 'h2' | 'h3' | 'body' | 'caption';
}

export interface ImageProps {
    url: BoundValue;
    alt?: BoundValue;
}

export interface ButtonProps {
    label: BoundValue;
    action?: Action;
}

export interface CardProps {
    title: BoundValue;
    children?: Children;
}

export interface RowProps {
    children?: Children;
}

export interface ColumnProps {
    children?: Children;
}

export interface ListProps {
    children?: Children;
}

export interface ListItemProps {
    title: BoundValue;
    subtitle?: BoundValue;
    leading?: BoundValue;
    trailing?: BoundValue;
}

// --- Messages ---

/**
 * surfaceUpdate message
 */
export interface SurfaceUpdate {
    surfaceUpdate: {
        surfaceId: string;
        components: A2UIComponent[];
    };
}

/**
 * dataModelUpdate message
 */
export interface DataModelUpdate {
    dataModelUpdate: {
        surfaceId: string;
        contents: Array<{
            key: string;
            valueString?: string;
            valueNumber?: number;
            valueBoolean?: boolean;
            valueMap?: Record<string, any>;
            valueList?: any[];
        }>;
    };
}

/**
 * beginRendering message
 */
export interface BeginRendering {
    beginRendering: {
        surfaceId: string;
        root: string;
        catalogId?: string;
    };
}

/**
 * deleteSurface message
 */
export interface DeleteSurface {
    deleteSurface: {
        surfaceId: string;
    };
}

/** A2UI Message union type */
export type A2UIMessage = SurfaceUpdate | DataModelUpdate | BeginRendering | DeleteSurface;

// --- Surface State ---

/**
 * Surface state for renderer
 */
export interface Surface {
    surfaceId: string;
    components: Map<string, A2UIComponent>;
    dataModel: Map<string, any>;
    rootId: string | null;
    isReady: boolean;
}

// --- Renderer Props ---

/**
 * Template rendering context for dynamic list items
 */
export interface TemplateContext {
    item: any;
    index: number;
}

/**
 * Standard props for all A2UI component renderers
 */
export interface RendererProps {
    component: A2UIComponent;
    surface: Surface;
    renderChildren: (childIds: string[]) => React.ReactNode;
    renderTemplate?: (componentId: string, dataPath: string) => React.ReactNode;
    templateContext?: TemplateContext;
}

// --- User Action ---

/**
 * userAction message sent from client to server
 */
export interface UserAction {
    name: string;
    surfaceId: string;
    sourceComponentId: string;
    timestamp: string;
    context: Record<string, any>;
}

// --- Catalog ---

/**
 * Standard catalog ID for A2UI v0.8
 */
export const STANDARD_CATALOG_ID = 'https://a2ui.org/specification/v0_8/standard_catalog_definition.json';

/**
 * Standard component types in A2UI v0.8
 */
export const STANDARD_COMPONENT_TYPES = [
    'Text',
    'Image',
    'Button',
    'Card',
    'Row',
    'Column',
    'List',
    'ListItem',
] as const;

export type StandardComponentType = typeof STANDARD_COMPONENT_TYPES[number];
