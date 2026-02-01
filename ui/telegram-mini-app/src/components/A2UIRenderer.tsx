/**
 * A2UI Renderer Component
 *
 * Renders A2UI SurfaceUpdate as React components.
 */

import { useMemo } from 'react';
import type {
  SurfaceUpdate,
  ComponentDefinition,
  Action,
  BoundValue,
  ExplicitList,
  PathReference,
} from '../types';
import { isLiteralString } from '../types';
import './A2UIRenderer.css';

// --- Props ---

interface A2UIRendererProps {
  surface: SurfaceUpdate;
  dataModel: Record<string, unknown>;
  onAction: (action: Action) => void;
  onDataUpdate: (path: string, value: unknown) => void;
  theme?: 'light' | 'dark';
}

// --- Main Renderer ---

export function A2UIRenderer({
  surface,
  dataModel,
  onAction,
  onDataUpdate,
  theme = 'light',
}: A2UIRendererProps) {
  // Build component map for ID lookup
  const componentMap = useMemo(() => {
    const map = new Map<string, ComponentDefinition>();
    for (const comp of surface.components) {
      map.set(comp.id, comp);
    }
    return map;
  }, [surface]);

  // Resolve bound value
  const resolveBoundValue = (value: BoundValue): string => {
    if (isLiteralString(value)) {
      return value.literalString;
    }

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
  };

  // Get data model value by path
  const getDataValue = (path: string): unknown => {
    const cleanPath = path.startsWith('/') ? path.slice(1) : path;
    const parts = cleanPath.split('/');
    let current: unknown = dataModel;

    for (const part of parts) {
      if (current && typeof current === 'object' && part in current) {
        current = (current as Record<string, unknown>)[part];
      } else {
        return undefined;
      }
    }

    return current;
  };

  // Resolve children IDs
  const resolveChildren = (children: ExplicitList | PathReference): string[] => {
    if ('explicitList' in children) {
      return children.explicitList;
    }
    const resolved = getDataValue(children.path);
    return Array.isArray(resolved) ? resolved.map(String) : [];
  };

  // Render single component
  const renderComponent = (def: ComponentDefinition): React.ReactNode => {
    const comp = def.component;

    // Text
    if ('Text' in comp) {
      const text = resolveBoundValue(comp.Text.text);
      const hint = comp.Text.usageHint || 'body';
      return (
        <div key={def.id} className={`a2ui-text a2ui-text--${hint}`}>
          {text}
        </div>
      );
    }

    // Button
    if ('Button' in comp) {
      const label = resolveBoundValue(comp.Button.label);
      const variant = comp.Button.variant || 'primary';
      return (
        <button
          key={def.id}
          className={`a2ui-button a2ui-button--${variant}`}
          disabled={comp.Button.disabled}
          onClick={() => onAction(comp.Button.action)}
        >
          {label}
        </button>
      );
    }

    // Image
    if ('Image' in comp) {
      const src = resolveBoundValue(comp.Image.src);
      const alt = comp.Image.alt ? resolveBoundValue(comp.Image.alt) : '';
      return (
        <img
          key={def.id}
          className="a2ui-image"
          src={src}
          alt={alt}
          width={comp.Image.width}
          height={comp.Image.height}
        />
      );
    }

    // Card
    if ('Card' in comp) {
      const title = resolveBoundValue(comp.Card.title);
      const subtitle = comp.Card.subtitle ? resolveBoundValue(comp.Card.subtitle) : null;
      const childIds = resolveChildren(comp.Card.children);
      return (
        <div key={def.id} className="a2ui-card">
          <div className="a2ui-card__header">
            <div className="a2ui-card__title">{title}</div>
            {subtitle && <div className="a2ui-card__subtitle">{subtitle}</div>}
          </div>
          <div className="a2ui-card__content">
            {childIds.map((id) => {
              const child = componentMap.get(id);
              return child ? renderComponent(child) : null;
            })}
          </div>
        </div>
      );
    }

    // Row
    if ('Row' in comp) {
      const childIds = resolveChildren(comp.Row.children);
      const gap = comp.Row.gap || 8;
      return (
        <div
          key={def.id}
          className="a2ui-row"
          style={{
            gap: `${gap}px`,
            alignItems: comp.Row.align || 'center',
            justifyContent: comp.Row.justify || 'start',
          }}
        >
          {childIds.map((id) => {
            const child = componentMap.get(id);
            return child ? renderComponent(child) : null;
          })}
        </div>
      );
    }

    // Column
    if ('Column' in comp) {
      const childIds = resolveChildren(comp.Column.children);
      const gap = comp.Column.gap || 8;
      return (
        <div
          key={def.id}
          className="a2ui-column"
          style={{
            gap: `${gap}px`,
            alignItems: comp.Column.align || 'stretch',
          }}
        >
          {childIds.map((id) => {
            const child = componentMap.get(id);
            return child ? renderComponent(child) : null;
          })}
        </div>
      );
    }

    // List
    if ('List' in comp) {
      const childIds = resolveChildren(comp.List.children);
      const style = comp.List.style || 'bullet';
      return (
        <ul key={def.id} className={`a2ui-list a2ui-list--${style}`}>
          {childIds.map((id) => {
            const child = componentMap.get(id);
            return child ? renderComponent(child) : null;
          })}
        </ul>
      );
    }

    // ListItem
    if ('ListItem' in comp) {
      const content = resolveBoundValue(comp.ListItem.content);
      return (
        <li
          key={def.id}
          className="a2ui-list-item"
          onClick={comp.ListItem.action ? () => onAction(comp.ListItem.action!) : undefined}
        >
          {content}
        </li>
      );
    }

    // TextField
    if ('TextField' in comp) {
      const label = resolveBoundValue(comp.TextField.label);
      const path = comp.TextField.value.path;
      const value = String(getDataValue(path) || '');
      const placeholder = comp.TextField.placeholder
        ? resolveBoundValue(comp.TextField.placeholder)
        : '';
      return (
        <div key={def.id} className="a2ui-field">
          <label className="a2ui-field__label">{label}</label>
          <input
            type={comp.TextField.type || 'text'}
            className="a2ui-field__input"
            value={value}
            placeholder={placeholder}
            required={comp.TextField.required}
            disabled={comp.TextField.disabled}
            onChange={(e) => onDataUpdate(path, e.target.value)}
          />
        </div>
      );
    }

    // TextArea
    if ('TextArea' in comp) {
      const label = resolveBoundValue(comp.TextArea.label);
      const path = comp.TextArea.value.path;
      const value = String(getDataValue(path) || '');
      const placeholder = comp.TextArea.placeholder
        ? resolveBoundValue(comp.TextArea.placeholder)
        : '';
      return (
        <div key={def.id} className="a2ui-field">
          <label className="a2ui-field__label">{label}</label>
          <textarea
            className="a2ui-field__textarea"
            value={value}
            placeholder={placeholder}
            rows={comp.TextArea.rows || 4}
            required={comp.TextArea.required}
            disabled={comp.TextArea.disabled}
            onChange={(e) => onDataUpdate(path, e.target.value)}
          />
        </div>
      );
    }

    // NumberInput
    if ('NumberInput' in comp) {
      const label = resolveBoundValue(comp.NumberInput.label);
      const path = comp.NumberInput.value.path;
      const value = getDataValue(path);
      return (
        <div key={def.id} className="a2ui-field">
          <label className="a2ui-field__label">{label}</label>
          <input
            type="number"
            className="a2ui-field__input"
            value={value !== undefined ? String(value) : ''}
            min={comp.NumberInput.min}
            max={comp.NumberInput.max}
            step={comp.NumberInput.step}
            required={comp.NumberInput.required}
            disabled={comp.NumberInput.disabled}
            onChange={(e) => onDataUpdate(path, Number(e.target.value))}
          />
        </div>
      );
    }

    // DateTimeInput
    if ('DateTimeInput' in comp) {
      const label = resolveBoundValue(comp.DateTimeInput.label);
      const path = comp.DateTimeInput.value.path;
      const value = String(getDataValue(path) || '');
      const mode = comp.DateTimeInput.mode || 'date';
      const inputType = mode === 'datetime' ? 'datetime-local' : mode;
      return (
        <div key={def.id} className="a2ui-field">
          <label className="a2ui-field__label">{label}</label>
          <input
            type={inputType}
            className="a2ui-field__input"
            value={value}
            min={comp.DateTimeInput.min}
            max={comp.DateTimeInput.max}
            required={comp.DateTimeInput.required}
            disabled={comp.DateTimeInput.disabled}
            onChange={(e) => onDataUpdate(path, e.target.value)}
          />
        </div>
      );
    }

    // Checkbox
    if ('Checkbox' in comp) {
      const label = resolveBoundValue(comp.Checkbox.label);
      const path = comp.Checkbox.value.path;
      const value = Boolean(getDataValue(path));
      return (
        <div key={def.id} className="a2ui-checkbox">
          <input
            type="checkbox"
            className="a2ui-checkbox__input"
            checked={value}
            disabled={comp.Checkbox.disabled}
            onChange={(e) => onDataUpdate(path, e.target.checked)}
          />
          <label className="a2ui-checkbox__label">{label}</label>
        </div>
      );
    }

    // Select
    if ('Select' in comp) {
      const label = resolveBoundValue(comp.Select.label);
      const path = comp.Select.value.path;
      const value = String(getDataValue(path) || '');
      const placeholder = comp.Select.placeholder
        ? resolveBoundValue(comp.Select.placeholder)
        : '';
      return (
        <div key={def.id} className="a2ui-field">
          <label className="a2ui-field__label">{label}</label>
          <select
            className="a2ui-field__select"
            value={value}
            required={comp.Select.required}
            disabled={comp.Select.disabled}
            onChange={(e) => onDataUpdate(path, e.target.value)}
          >
            {placeholder && (
              <option value="" disabled>
                {placeholder}
              </option>
            )}
            {comp.Select.options.map((opt, i) => (
              <option key={i} value={opt.value}>
                {isLiteralString(opt.label) ? opt.label.literalString : ''}
              </option>
            ))}
          </select>
        </div>
      );
    }

    // Divider
    if ('Divider' in comp) {
      return <hr key={def.id} className="a2ui-divider" />;
    }

    // Spacer
    if ('Spacer' in comp) {
      return <div key={def.id} style={{ height: comp.Spacer.height }} />;
    }

    return null;
  };

  return (
    <div className={`a2ui-renderer a2ui-renderer--${theme}`}>
      {surface.components.map((def) => renderComponent(def))}
    </div>
  );
}
