/**
 * A2UI Module
 *
 * Provides types, state management, and utilities for A2UI (Agent-driven UI).
 *
 * @example
 * ```ts
 * import {
 *   A2UIStateManager,
 *   SurfaceUpdate,
 *   isTextComponent,
 *   resolveBoundValue,
 * } from './a2ui';
 *
 * const state = new A2UIStateManager();
 * state.processMessage(surfaceUpdate);
 * ```
 */

// Types
export {
  // BoundValue types
  BoundValue,
  LiteralString,
  PathReference,
  isLiteralString,
  isPathReference,
  resolveBoundValue,
  // Action types
  Action,
  ActionContext,
  // Component types
  A2UIComponentType,
  ComponentDefinition,
  ExplicitList,
  TextComponent,
  ButtonComponent,
  ImageComponent,
  CardComponent,
  RowComponent,
  ColumnComponent,
  ListComponent,
  ListItemComponent,
  TextFieldComponent,
  TextAreaComponent,
  NumberInputComponent,
  DateTimeInputComponent,
  CheckboxComponent,
  SelectComponent,
  SelectOption,
  DividerComponent,
  SpacerComponent,
  // Message types
  A2UIMessage,
  SurfaceUpdate,
  BeginRendering,
  DataModelUpdate,
  // Message type guards
  isSurfaceUpdate,
  isBeginRendering,
  isDataModelUpdate,
  // Component type guards
  isTextComponent,
  isButtonComponent,
  isImageComponent,
  isCardComponent,
  isRowComponent,
  isColumnComponent,
  isListComponent,
  isListItemComponent,
  isTextFieldComponent,
  isTextAreaComponent,
  isNumberInputComponent,
  isDateTimeInputComponent,
  isCheckboxComponent,
  isSelectComponent,
  isDividerComponent,
  isSpacerComponent,
  // Utility functions
  isFormInputComponent,
  getComponentTypeName,
} from './types.js';

// State management
export {
  A2UIStateManager,
  createA2UIStateManager,
  SurfaceState,
  DataModelState,
  A2UIStateEvents,
} from './state.js';
