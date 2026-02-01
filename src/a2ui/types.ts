/**
 * A2UI (Agent-driven UI) Type Definitions
 *
 * A2UI is a declarative UI specification that allows AI agents to generate
 * dynamic user interfaces. Components are defined as JSON and can be rendered
 * by different frontends (Web, Telegram, etc.)
 *
 * @see https://a2ui.org/
 */

// --- Bound Values ---

/**
 * A literal string value
 */
export interface LiteralString {
  literalString: string;
}

/**
 * A path reference to a data model value
 */
export interface PathReference {
  path: string;
}

/**
 * A value that can be either a literal string or a reference to data model
 */
export type BoundValue = LiteralString | PathReference;

/**
 * Type guard for LiteralString
 */
export function isLiteralString(value: BoundValue): value is LiteralString {
  return 'literalString' in value;
}

/**
 * Type guard for PathReference
 */
export function isPathReference(value: BoundValue): value is PathReference {
  return 'path' in value;
}

/**
 * Resolve a BoundValue to its string value
 */
export function resolveBoundValue(
  value: BoundValue,
  dataModel?: Record<string, unknown>
): string {
  if (isLiteralString(value)) {
    return value.literalString;
  }

  if (!dataModel) {
    return '';
  }

  // Simple path resolution (supports /foo/bar format)
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

// --- Actions ---

/**
 * Context item for actions
 */
export interface ActionContext {
  key: string;
  value: BoundValue;
}

/**
 * Action triggered by user interaction
 */
export interface Action {
  /** Action name/identifier */
  name: string;
  /** Context data to include with the action */
  context?: ActionContext[];
}

// --- Component Types ---

/**
 * Text component - displays text content
 */
export interface TextComponent {
  Text: {
    /** Text content */
    text: BoundValue;
    /** Usage hint for rendering (h1, h2, body, caption, etc.) */
    usageHint?: 'h1' | 'h2' | 'h3' | 'body' | 'caption' | 'label';
  };
}

/**
 * Button component - triggers actions
 */
export interface ButtonComponent {
  Button: {
    /** Button label */
    label: BoundValue;
    /** Action to trigger when clicked */
    action: Action;
    /** Button style variant */
    variant?: 'primary' | 'secondary' | 'danger' | 'link';
    /** Whether the button is disabled */
    disabled?: boolean;
  };
}

/**
 * Image component - displays an image
 */
export interface ImageComponent {
  Image: {
    /** Image URL */
    src: BoundValue;
    /** Alt text for accessibility */
    alt?: BoundValue;
    /** Image width */
    width?: number;
    /** Image height */
    height?: number;
  };
}

/**
 * Card component - container with title
 */
export interface CardComponent {
  Card: {
    /** Card title */
    title: BoundValue;
    /** Child component IDs */
    children: ExplicitList | PathReference;
    /** Optional subtitle */
    subtitle?: BoundValue;
    /** Optional header image */
    headerImage?: BoundValue;
  };
}

/**
 * Row component - horizontal layout
 */
export interface RowComponent {
  Row: {
    /** Child component IDs */
    children: ExplicitList | PathReference;
    /** Gap between children */
    gap?: number;
    /** Alignment */
    align?: 'start' | 'center' | 'end' | 'stretch';
    /** Justify content */
    justify?: 'start' | 'center' | 'end' | 'between' | 'around';
  };
}

/**
 * Column component - vertical layout
 */
export interface ColumnComponent {
  Column: {
    /** Child component IDs */
    children: ExplicitList | PathReference;
    /** Gap between children */
    gap?: number;
    /** Alignment */
    align?: 'start' | 'center' | 'end' | 'stretch';
  };
}

/**
 * List component - displays a list of items
 */
export interface ListComponent {
  List: {
    /** Child component IDs */
    children: ExplicitList | PathReference;
    /** List style */
    style?: 'bullet' | 'number' | 'none';
  };
}

/**
 * ListItem component - single list item
 */
export interface ListItemComponent {
  ListItem: {
    /** Item content */
    content: BoundValue;
    /** Optional icon */
    icon?: BoundValue;
    /** Optional action on click */
    action?: Action;
  };
}

/**
 * TextField component - text input
 */
export interface TextFieldComponent {
  TextField: {
    /** Field label */
    label: BoundValue;
    /** Bound value (path to data model) */
    value: PathReference;
    /** Placeholder text */
    placeholder?: BoundValue;
    /** Whether the field is required */
    required?: boolean;
    /** Input type */
    type?: 'text' | 'email' | 'password' | 'url' | 'tel';
    /** Whether the field is disabled */
    disabled?: boolean;
  };
}

/**
 * TextArea component - multi-line text input
 */
export interface TextAreaComponent {
  TextArea: {
    /** Field label */
    label: BoundValue;
    /** Bound value (path to data model) */
    value: PathReference;
    /** Placeholder text */
    placeholder?: BoundValue;
    /** Number of rows */
    rows?: number;
    /** Whether the field is required */
    required?: boolean;
    /** Whether the field is disabled */
    disabled?: boolean;
  };
}

/**
 * NumberInput component - numeric input
 */
export interface NumberInputComponent {
  NumberInput: {
    /** Field label */
    label: BoundValue;
    /** Bound value (path to data model) */
    value: PathReference;
    /** Minimum value */
    min?: number;
    /** Maximum value */
    max?: number;
    /** Step increment */
    step?: number;
    /** Whether the field is required */
    required?: boolean;
    /** Whether the field is disabled */
    disabled?: boolean;
  };
}

/**
 * DateTimeInput component - date/time picker
 */
export interface DateTimeInputComponent {
  DateTimeInput: {
    /** Field label */
    label: BoundValue;
    /** Bound value (path to data model) */
    value: PathReference;
    /** Input mode */
    mode?: 'date' | 'time' | 'datetime';
    /** Minimum date/time */
    min?: string;
    /** Maximum date/time */
    max?: string;
    /** Whether the field is required */
    required?: boolean;
    /** Whether the field is disabled */
    disabled?: boolean;
  };
}

/**
 * Checkbox component
 */
export interface CheckboxComponent {
  Checkbox: {
    /** Field label */
    label: BoundValue;
    /** Bound value (path to data model) */
    value: PathReference;
    /** Whether the checkbox is disabled */
    disabled?: boolean;
  };
}

/**
 * Select component - dropdown selection
 */
export interface SelectComponent {
  Select: {
    /** Field label */
    label: BoundValue;
    /** Bound value (path to data model) */
    value: PathReference;
    /** Options */
    options: SelectOption[];
    /** Placeholder text */
    placeholder?: BoundValue;
    /** Whether the field is required */
    required?: boolean;
    /** Whether the field is disabled */
    disabled?: boolean;
  };
}

/**
 * Select option
 */
export interface SelectOption {
  /** Option value */
  value: string;
  /** Display label */
  label: BoundValue;
}

/**
 * Divider component - horizontal line
 */
export interface DividerComponent {
  Divider: {
    /** Divider style */
    style?: 'solid' | 'dashed' | 'dotted';
  };
}

/**
 * Spacer component - adds vertical space
 */
export interface SpacerComponent {
  Spacer: {
    /** Height in pixels */
    height: number;
  };
}

// --- Component Union ---

/**
 * All supported A2UI components
 */
export type A2UIComponentType =
  | TextComponent
  | ButtonComponent
  | ImageComponent
  | CardComponent
  | RowComponent
  | ColumnComponent
  | ListComponent
  | ListItemComponent
  | TextFieldComponent
  | TextAreaComponent
  | NumberInputComponent
  | DateTimeInputComponent
  | CheckboxComponent
  | SelectComponent
  | DividerComponent
  | SpacerComponent;

// --- Component Definition ---

/**
 * Explicit list of component IDs
 */
export interface ExplicitList {
  explicitList: string[];
}

/**
 * A component definition with ID
 */
export interface ComponentDefinition {
  /** Unique component ID */
  id: string;
  /** Component specification */
  component: A2UIComponentType;
}

// --- Surface Update ---

/**
 * Surface update message - defines components for a surface
 */
export interface SurfaceUpdate {
  type: 'surfaceUpdate';
  /** Surface ID (e.g., 'main', 'sidebar') */
  surfaceId: string;
  /** List of component definitions */
  components: ComponentDefinition[];
}

/**
 * Begin rendering message - signals start of rendering
 */
export interface BeginRendering {
  type: 'beginRendering';
  /** Surface ID to render */
  surfaceId: string;
  /** Root component ID (optional, defaults to first component) */
  root?: string;
}

/**
 * Data model update message - updates data model values
 */
export interface DataModelUpdate {
  type: 'dataModelUpdate';
  /** Model ID */
  modelId: string;
  /** Updated data */
  data: Record<string, unknown>;
}

/**
 * Union of all A2UI message types
 */
export type A2UIMessage = SurfaceUpdate | BeginRendering | DataModelUpdate;

// --- Type Guards ---

/**
 * Check if message is a SurfaceUpdate
 */
export function isSurfaceUpdate(msg: A2UIMessage): msg is SurfaceUpdate {
  return msg.type === 'surfaceUpdate';
}

/**
 * Check if message is a BeginRendering
 */
export function isBeginRendering(msg: A2UIMessage): msg is BeginRendering {
  return msg.type === 'beginRendering';
}

/**
 * Check if message is a DataModelUpdate
 */
export function isDataModelUpdate(msg: A2UIMessage): msg is DataModelUpdate {
  return msg.type === 'dataModelUpdate';
}

// --- Component Type Guards ---

export function isTextComponent(c: A2UIComponentType): c is TextComponent {
  return 'Text' in c;
}

export function isButtonComponent(c: A2UIComponentType): c is ButtonComponent {
  return 'Button' in c;
}

export function isImageComponent(c: A2UIComponentType): c is ImageComponent {
  return 'Image' in c;
}

export function isCardComponent(c: A2UIComponentType): c is CardComponent {
  return 'Card' in c;
}

export function isRowComponent(c: A2UIComponentType): c is RowComponent {
  return 'Row' in c;
}

export function isColumnComponent(c: A2UIComponentType): c is ColumnComponent {
  return 'Column' in c;
}

export function isListComponent(c: A2UIComponentType): c is ListComponent {
  return 'List' in c;
}

export function isListItemComponent(c: A2UIComponentType): c is ListItemComponent {
  return 'ListItem' in c;
}

export function isTextFieldComponent(c: A2UIComponentType): c is TextFieldComponent {
  return 'TextField' in c;
}

export function isTextAreaComponent(c: A2UIComponentType): c is TextAreaComponent {
  return 'TextArea' in c;
}

export function isNumberInputComponent(c: A2UIComponentType): c is NumberInputComponent {
  return 'NumberInput' in c;
}

export function isDateTimeInputComponent(c: A2UIComponentType): c is DateTimeInputComponent {
  return 'DateTimeInput' in c;
}

export function isCheckboxComponent(c: A2UIComponentType): c is CheckboxComponent {
  return 'Checkbox' in c;
}

export function isSelectComponent(c: A2UIComponentType): c is SelectComponent {
  return 'Select' in c;
}

export function isDividerComponent(c: A2UIComponentType): c is DividerComponent {
  return 'Divider' in c;
}

export function isSpacerComponent(c: A2UIComponentType): c is SpacerComponent {
  return 'Spacer' in c;
}

/**
 * Check if component requires form input (used for Telegram adaptive rendering)
 */
export function isFormInputComponent(c: A2UIComponentType): boolean {
  return (
    isTextFieldComponent(c) ||
    isTextAreaComponent(c) ||
    isNumberInputComponent(c) ||
    isDateTimeInputComponent(c) ||
    isCheckboxComponent(c) ||
    isSelectComponent(c)
  );
}

/**
 * Get the component type name
 */
export function getComponentTypeName(c: A2UIComponentType): string {
  if (isTextComponent(c)) return 'Text';
  if (isButtonComponent(c)) return 'Button';
  if (isImageComponent(c)) return 'Image';
  if (isCardComponent(c)) return 'Card';
  if (isRowComponent(c)) return 'Row';
  if (isColumnComponent(c)) return 'Column';
  if (isListComponent(c)) return 'List';
  if (isListItemComponent(c)) return 'ListItem';
  if (isTextFieldComponent(c)) return 'TextField';
  if (isTextAreaComponent(c)) return 'TextArea';
  if (isNumberInputComponent(c)) return 'NumberInput';
  if (isDateTimeInputComponent(c)) return 'DateTimeInput';
  if (isCheckboxComponent(c)) return 'Checkbox';
  if (isSelectComponent(c)) return 'Select';
  if (isDividerComponent(c)) return 'Divider';
  if (isSpacerComponent(c)) return 'Spacer';
  return 'Unknown';
}
