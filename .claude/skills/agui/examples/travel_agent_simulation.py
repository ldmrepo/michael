from typing import List, Dict, Any, Optional

class AgUiMessageBuilder:
    """
    Helper class to build AG-UI protocol messages.
    Simulating the message structure for a Python-based agent.
    """
    
    def __init__(self):
        self.messages = []

    def render_component(self, component_name: str, props: Dict[str, Any], interaction_id: str = None) -> 'AgUiMessageBuilder':
        """
        Agent requests to render a UI component.
        """
        msg = {
            "type": "render",
            "component": component_name,
            "props": props,
            "timestamp": "2024-01-01T12:00:00Z"
        }
        if interaction_id:
            msg["interactionId"] = interaction_id
        
        self.messages.append(msg)
        return self

    def update_status(self, status: str) -> 'AgUiMessageBuilder':
        """
        Update agent status (e.g., 'thinking', 'awaiting_input').
        """
        msg = {
            "type": "status_update",
            "status": status
        }
        self.messages.append(msg)
        return self

    def build(self) -> List[Dict[str, Any]]:
        return self.messages

# --- Example Usage ---

def travel_agent_response():
    builder = AgUiMessageBuilder()
    
    # 1. Agent signals it is processing
    builder.update_status("thinking")
    
    # 2. Agent decides to ask user for preferences using a UI form
    builder.render_component(
        component_name="TravelPreferencesForm",
        props={
            "destinations": ["Paris", "Tokyo", "New York"],
            "budgetRange": [1000, 10000]
        },
        interaction_id="req-001"
    )
    
    # 3. Agent waits for user input
    builder.update_status("awaiting_input")
    
    return builder.build()

if __name__ == "__main__":
    import json
    print(json.dumps(travel_agent_response(), indent=2))
