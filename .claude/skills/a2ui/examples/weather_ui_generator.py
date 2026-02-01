import json
from typing import Dict, Any, List

class A2UIBuilder:
    """Helper class to build A2UI messages."""
    def __init__(self):
        self.messages = []

    def add_component(
        self, 
        id: str, 
        type: str, 
        parent_id: str, 
        props: Dict[str, Any] = None
    ) -> 'A2UIBuilder':
        """Adds a component definition to the stream."""
        msg = {
            "type": "component",
            "id": id,
            "componentType": type,
            "parentId": parent_id,
            "props": props or {}
        }
        self.messages.append(msg)
        return self

    def update_state(self, path: str, value: Any) -> 'A2UIBuilder':
        """Updates the shared state."""
        msg = {
            "type": "state",
            "path": path,
            "value": value
        }
        self.messages.append(msg)
        return self

    def to_json(self) -> str:
        """Returns the messages as a JSON string."""
        return json.dumps(self.messages, indent=2)

    def build(self) -> List[Dict[str, Any]]:
        """Returns the list of messages."""
        return self.messages

def generate_demo_ui():
    """Generates a demo UI for a weather dashboard."""
    builder = A2UIBuilder()
    
    # 1. Root Layout
    builder.add_component(
        id="root-container",
        type="Container",
        parent_id="root",
        props={"layout": "vertical", "padding": "20px", "gap": "10px"}
    )
    
    # 2. Header
    builder.add_component(
        id="header",
        type="Text",
        parent_id="root-container",
        props={"text": "Seoul Weather Dashboard", "variant": "h1"}
    )
    
    # 3. Weather Card Container
    builder.add_component(
        id="weather-card",
        type="Card",
        parent_id="root-container",
        props={"elevation": 2}
    )
    
    # 4. Content inside Card
    builder.add_component(
        id="weather-info",
        type="Text",
        parent_id="weather-card",
        props={"text": "Current Temperature: 25°C", "variant": "body1"}
    )
    
    # 5. Refresh Button
    builder.add_component(
        id="refresh-btn",
        type="Button",
        parent_id="root-container",
        props={
            "label": "Refresh Data", 
            "variant": "primary",
            "onClick": {"action": "refresh_weather"}
        }
    )
    
    return builder.to_json()

if __name__ == "__main__":
    print(generate_demo_ui())
