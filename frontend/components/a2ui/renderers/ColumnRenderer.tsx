/**
 * A2UI Column Component Renderer (Vertical Layout)
 * @see https://a2ui.org/specification/v0.8-a2ui/#column
 */

import { RendererProps, ColumnProps } from '../types';
import { getComponentProps, getChildrenIds } from '../utils';

export function ColumnRenderer({ component, surface, renderChildren }: RendererProps) {
    const props = getComponentProps<ColumnProps>(component);
    const childIds = getChildrenIds(props.children);

    return (
        <div className="flex flex-col gap-4">
            {renderChildren(childIds)}
        </div>
    );
}
