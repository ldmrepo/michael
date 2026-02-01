/**
 * A2UI Image Component Renderer
 * @see https://a2ui.org/specification/v0.8-a2ui/#image
 */

import { RendererProps, ImageProps } from '../types';
import { resolveBoundValue, getComponentProps } from '../utils';

export function ImageRenderer({ component, surface }: RendererProps) {
    const props = getComponentProps<ImageProps>(component);
    const url = String(resolveBoundValue(props.url, surface.dataModel));
    const alt = String(resolveBoundValue(props.alt, surface.dataModel) || '');

    if (!url) return null;

    return (
        <img
            src={url}
            alt={alt}
            className="rounded-lg max-w-full"
        />
    );
}
