/**
 * A2UI Button Component Renderer
 * @see https://a2ui.org/specification/v0.8-a2ui/#button
 */

import { RendererProps, ButtonProps } from '../types';
import { resolveBoundValue, getComponentProps, resolveActionContext } from '../utils';

// Global action handler - set by page component
let globalActionHandler: ((actionName: string, context: Record<string, any>) => Promise<void>) | null = null;

/**
 * Set the global action handler for button clicks
 * This should be called by the page component to handle actions via AG-UI stream
 */
export function setActionHandler(handler: (actionName: string, context: Record<string, any>) => Promise<void>) {
    globalActionHandler = handler;
}

/**
 * Clear the global action handler
 */
export function clearActionHandler() {
    globalActionHandler = null;
}

export function ButtonRenderer({ component, surface }: RendererProps) {
    const props = getComponentProps<ButtonProps>(component);
    const label = resolveBoundValue(props.label, surface.dataModel);
    const action = props.action;

    const handleClick = async () => {
        if (!action) return;

        const resolvedContext = resolveActionContext(action.context, surface.dataModel);

        if (globalActionHandler) {
            // Use AG-UI stream handler (standard approach)
            await globalActionHandler(action.name, resolvedContext);
        } else {
            // Fallback: log to console
            console.log('Action triggered:', action.name, resolvedContext);
        }
    };

    return (
        <button
            onClick={handleClick}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors"
        >
            {label}
        </button>
    );
}
