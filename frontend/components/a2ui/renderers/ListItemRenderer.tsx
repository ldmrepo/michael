/**
 * A2UI ListItem Component Renderer
 * @see https://a2ui.org/specification/v0.8-a2ui/#listitem
 */

import { RendererProps, ListItemProps } from '../types';
import { resolveBoundValue, getComponentProps } from '../utils';

export function ListItemRenderer({ component, surface }: RendererProps) {
    const props = getComponentProps<ListItemProps>(component);

    const title = resolveBoundValue(props.title, surface.dataModel);
    const subtitle = resolveBoundValue(props.subtitle, surface.dataModel);
    const leading = resolveBoundValue(props.leading, surface.dataModel);
    const trailing = resolveBoundValue(props.trailing, surface.dataModel);

    return (
        <div className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
            {leading && (
                <span className="text-2xl flex-shrink-0">{leading}</span>
            )}
            <div className="flex-1 min-w-0">
                <div className="flex justify-between items-start gap-2">
                    <span className="font-medium text-gray-800">{title}</span>
                    {trailing && (
                        <span className="text-sm font-semibold text-indigo-600 whitespace-nowrap">
                            {trailing}
                        </span>
                    )}
                </div>
                {subtitle && (
                    <p className="text-sm text-gray-500 mt-0.5">{subtitle}</p>
                )}
            </div>
        </div>
    );
}
