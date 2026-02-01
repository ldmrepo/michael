/**
 * A2UI List Component Renderer
 * @see https://a2ui.org/specification/v0.8-a2ui/#list
 */

import { RendererProps, ListProps } from '../types';
import { getComponentProps, getChildrenIds } from '../utils';

export function ListRenderer({ component, surface, renderChildren, renderTemplate }: RendererProps) {
    const props = getComponentProps<ListProps>(component);

    // Support template-based rendering for dynamic lists
    if (props.children?.template && renderTemplate) {
        const { dataPath, componentId } = props.children.template;
        return (
            <div className="space-y-2">
                {renderTemplate(componentId, dataPath)}
            </div>
        );
    }

    // Explicit list rendering
    const childIds = getChildrenIds(props.children);

    return (
        <div className="space-y-2">
            {renderChildren(childIds)}
        </div>
    );
}
