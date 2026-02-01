/**
 * A2UI Text Component Renderer
 * @see https://a2ui.org/specification/v0.8-a2ui/#text
 */

import { RendererProps, TextProps } from '../types';
import { resolveBoundValue, getComponentProps } from '../utils';

const USAGE_HINT_STYLES: Record<string, string> = {
    h1: 'text-2xl font-bold text-gray-900',
    h2: 'text-xl font-semibold text-gray-800',
    h3: 'text-lg font-medium text-gray-700',
    body: 'text-gray-600',
    caption: 'text-sm text-gray-500',
};

export function TextRenderer({ component, surface }: RendererProps) {
    const props = getComponentProps<TextProps>(component);
    const text = resolveBoundValue(props.text, surface.dataModel);
    const usageHint = props.usageHint || 'body';

    const className = USAGE_HINT_STYLES[usageHint] || USAGE_HINT_STYLES.body;

    return <p className={className}>{text}</p>;
}
