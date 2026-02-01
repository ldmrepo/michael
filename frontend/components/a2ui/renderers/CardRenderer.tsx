/**
 * A2UI Card Component Renderer
 * @see https://a2ui.org/specification/v0.8-a2ui/#card
 */

import { RendererProps, CardProps } from '../types';
import { resolveBoundValue, getComponentProps, getChildrenIds } from '../utils';

export function CardRenderer({ component, surface, renderChildren }: RendererProps) {
    const props = getComponentProps<CardProps>(component);
    const title = resolveBoundValue(props.title, surface.dataModel);
    const childIds = getChildrenIds(props.children);

    return (
        <div className="bg-white rounded-xl p-5 shadow-lg">
            {title && (
                <h3 className="text-lg font-bold text-gray-800 mb-3">{title}</h3>
            )}
            <div className="space-y-2">
                {renderChildren(childIds)}
            </div>
        </div>
    );
}
