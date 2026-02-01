/**
 * A2UI Type Definitions for Mini App
 *
 * Simplified version of the main A2UI types for frontend use.
 */

// --- Bound Values ---

export interface LiteralString {
  literalString: string;
}

export interface PathReference {
  path: string;
}

export type BoundValue = LiteralString | PathReference;

export function isLiteralString(value: BoundValue): value is LiteralString {
  return 'literalString' in value;
}

export function isPathReference(value: BoundValue): value is PathReference {
  return 'path' in value;
}

// --- Actions ---

export interface ActionContext {
  key: string;
  value: BoundValue;
}

export interface Action {
  name: string;
  context?: ActionContext[];
}

// --- Component Types ---

export interface TextComponent {
  Text: {
    text: BoundValue;
    usageHint?: 'h1' | 'h2' | 'h3' | 'body' | 'caption' | 'label';
  };
}

export interface ButtonComponent {
  Button: {
    label: BoundValue;
    action: Action;
    variant?: 'primary' | 'secondary' | 'danger' | 'link';
    disabled?: boolean;
  };
}

export interface ImageComponent {
  Image: {
    src: BoundValue;
    alt?: BoundValue;
    width?: number;
    height?: number;
  };
}

export interface CardComponent {
  Card: {
    title: BoundValue;
    children: ExplicitList | PathReference;
    subtitle?: BoundValue;
    headerImage?: BoundValue;
  };
}

export interface RowComponent {
  Row: {
    children: ExplicitList | PathReference;
    gap?: number;
    align?: 'start' | 'center' | 'end' | 'stretch';
    justify?: 'start' | 'center' | 'end' | 'between' | 'around';
  };
}

export interface ColumnComponent {
  Column: {
    children: ExplicitList | PathReference;
    gap?: number;
    align?: 'start' | 'center' | 'end' | 'stretch';
  };
}

export interface ListComponent {
  List: {
    children: ExplicitList | PathReference;
    style?: 'bullet' | 'number' | 'none';
  };
}

export interface ListItemComponent {
  ListItem: {
    content: BoundValue;
    icon?: BoundValue;
    action?: Action;
  };
}

export interface TextFieldComponent {
  TextField: {
    label: BoundValue;
    value: PathReference;
    placeholder?: BoundValue;
    required?: boolean;
    type?: 'text' | 'email' | 'password' | 'url' | 'tel';
    disabled?: boolean;
  };
}

export interface TextAreaComponent {
  TextArea: {
    label: BoundValue;
    value: PathReference;
    placeholder?: BoundValue;
    rows?: number;
    required?: boolean;
    disabled?: boolean;
  };
}

export interface NumberInputComponent {
  NumberInput: {
    label: BoundValue;
    value: PathReference;
    min?: number;
    max?: number;
    step?: number;
    required?: boolean;
    disabled?: boolean;
  };
}

export interface DateTimeInputComponent {
  DateTimeInput: {
    label: BoundValue;
    value: PathReference;
    mode?: 'date' | 'time' | 'datetime';
    min?: string;
    max?: string;
    required?: boolean;
    disabled?: boolean;
  };
}

export interface CheckboxComponent {
  Checkbox: {
    label: BoundValue;
    value: PathReference;
    disabled?: boolean;
  };
}

export interface SelectComponent {
  Select: {
    label: BoundValue;
    value: PathReference;
    options: SelectOption[];
    placeholder?: BoundValue;
    required?: boolean;
    disabled?: boolean;
  };
}

export interface SelectOption {
  value: string;
  label: BoundValue;
}

export interface DividerComponent {
  Divider: {
    style?: 'solid' | 'dashed' | 'dotted';
  };
}

export interface SpacerComponent {
  Spacer: {
    height: number;
  };
}

// --- Component Union ---

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

export interface ExplicitList {
  explicitList: string[];
}

export interface ComponentDefinition {
  id: string;
  component: A2UIComponentType;
}

// --- Surface Update ---

export interface SurfaceUpdate {
  type: 'surfaceUpdate';
  surfaceId: string;
  components: ComponentDefinition[];
}
