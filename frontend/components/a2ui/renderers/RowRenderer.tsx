/**
 * A2UI Row Component Renderer (Horizontal Layout)
 * @see https://a2ui.org/specification/v0.8-a2ui/#row
 */

import { RendererProps, RowProps } from '../types';
import { getComponentProps, getChildrenIds } from '../utils';

export function RowRenderer({ component, surface, renderChildren }: RendererProps) {
    const props = getComponentProps<RowProps>(component);
    const childIds = getChildrenIds(props.children);

    return (
        <div className="flex flex-row gap-4">
            {renderChildren(childIds)}
        </div>
    );
}
