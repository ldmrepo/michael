/**
 * A2UI v0.8 Renderer Engine
 *
 * Main rendering component that:
 * 1. Builds component tree from adjacency list
 * 2. Resolves BoundValues from data model
 * 3. Renders standard catalog components
 *
 * @see https://a2ui.org/specification/v0.8-a2ui/
 */

'use client';

import React from 'react';
import { Surface, RendererProps, A2UIComponent, StandardComponentType, TemplateContext } from './types';
import { getComponentType, getNestedValue } from './utils';
import {
    TextRenderer,
    ImageRenderer,
    ButtonRenderer,
    CardRenderer,
    RowRenderer,
    ColumnRenderer,
    ListRenderer,
    ListItemRenderer,
} from './renderers';

/**
 * Component registry mapping component types to their renderers
 */
const COMPONENT_REGISTRY: Record<
    StandardComponentType,
    React.ComponentType<RendererProps>
> = {
    Text: TextRenderer,
    Image: ImageRenderer,
    Button: ButtonRenderer,
    Card: CardRenderer,
    Row: RowRenderer,
    Column: ColumnRenderer,
    List: ListRenderer,
    ListItem: ListItemRenderer,
};

/**
 * Fallback renderer for unknown component types
 */
function UnknownRenderer({ component }: { component: A2UIComponent }) {
    const type = getComponentType(component);
    return (
        <div className="p-2 bg-yellow-50 border border-yellow-200 rounded text-sm text-yellow-800">
            Unknown component type: {type}
        </div>
    );
}

/**
 * Error renderer for missing components
 */
function MissingRenderer({ componentId }: { componentId: string }) {
    return (
        <div className="p-2 bg-red-50 border border-red-200 rounded text-sm text-red-600">
            Component not found: {componentId}
        </div>
    );
}

/**
 * Props for A2UIRenderer
 */
interface A2UIRendererProps {
    surface: Surface;
    customRenderers?: Record<string, React.ComponentType<RendererProps>>;
}

/**
 * A2UI v0.8 Renderer Engine
 *
 * Renders a surface by:
 * 1. Starting from the root component
 * 2. Recursively rendering children using adjacency list model
 * 3. Resolving BoundValues against the data model
 * 4. Supports template-based dynamic list rendering
 */
export function A2UIRenderer({ surface, customRenderers = {} }: A2UIRendererProps) {
    // Don't render until beginRendering is received
    if (!surface.isReady || !surface.rootId) {
        return null;
    }

    /**
     * Recursively render a component and its children
     */
    const renderComponent = (
        componentId: string,
        templateContext?: TemplateContext
    ): React.ReactNode => {
        const component = surface.components.get(componentId);

        if (!component) {
            return <MissingRenderer key={componentId} componentId={componentId} />;
        }

        const componentType = getComponentType(component) as StandardComponentType;

        // Look up renderer: custom > standard > unknown
        const Renderer =
            customRenderers[componentType] ||
            COMPONENT_REGISTRY[componentType] ||
            null;

        if (!Renderer) {
            return <UnknownRenderer key={component.id} component={component} />;
        }

        // Function to render explicit children (passed to container components)
        const renderChildren = (childIds: string[]): React.ReactNode => {
            return childIds.map((id) => renderComponent(id, templateContext));
        };

        /**
         * Function to render template-based children
         * Used for dynamic lists where items come from data model
         */
        const renderTemplate = (templateComponentId: string, dataPath: string): React.ReactNode => {
            const items = getNestedValue(surface.dataModel, dataPath);

            if (!Array.isArray(items)) {
                return null;
            }

            return items.map((item, index) => {
                // Create a scoped data model for template rendering
                const scopedDataModel = new Map(surface.dataModel);
                // Add current item data at the root level for path resolution
                Object.entries(item as Record<string, any>).forEach(([key, value]) => {
                    scopedDataModel.set(key, value);
                });

                // Create scoped surface with item data
                const scopedSurface: Surface = {
                    ...surface,
                    dataModel: scopedDataModel,
                };

                const templateComponent = surface.components.get(templateComponentId);
                if (!templateComponent) {
                    return <MissingRenderer key={`${templateComponentId}-${index}`} componentId={templateComponentId} />;
                }

                const templateType = getComponentType(templateComponent) as StandardComponentType;
                const TemplateRenderer =
                    customRenderers[templateType] ||
                    COMPONENT_REGISTRY[templateType] ||
                    null;

                if (!TemplateRenderer) {
                    return <UnknownRenderer key={`${templateComponent.id}-${index}`} component={templateComponent} />;
                }

                const itemTemplateContext: TemplateContext = { item, index };

                return (
                    <TemplateRenderer
                        key={`${templateComponent.id}-${index}`}
                        component={templateComponent}
                        surface={scopedSurface}
                        renderChildren={(childIds) => childIds.map((id) => renderComponent(id, itemTemplateContext))}
                        renderTemplate={renderTemplate}
                        templateContext={itemTemplateContext}
                    />
                );
            });
        };

        const key = templateContext
            ? `${component.id}-${templateContext.index}`
            : component.id;

        return (
            <Renderer
                key={key}
                component={component}
                surface={surface}
                renderChildren={renderChildren}
                renderTemplate={renderTemplate}
                templateContext={templateContext}
            />
        );
    };

    return (
        <div className="a2ui-surface flex flex-col gap-4 w-full">
            {renderComponent(surface.rootId)}
        </div>
    );
}

export default A2UIRenderer;
