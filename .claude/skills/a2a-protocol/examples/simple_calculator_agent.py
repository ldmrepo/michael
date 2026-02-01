import uvicorn
import asyncio
from typing import Any
from a2a.types import (
    AgentCapabilities, 
    AgentSkill, 
    AgentCard, 
    ContentTypes,
    Part,
    TextPart,
    Task
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.apps import A2AStarletteApplication
from a2a.server.tasks import InMemoryTaskStore
from a2a.utils import completed_task, new_artifact

# --- 1. Agent Logic (Executor) ---
class CalculatorExecutor(AgentExecutor):
    """
    A simple executor that acts as a calculator.
    In a real agent, this would call an LLM or complex business logic.
    """
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_input = context.get_user_input()
        print(f"[Executor] Received input: {user_input}")
        
        # Simple logic: try to evaluate math, else echo
        try:
            # WARNING: eval is unsafe in prod, using for demo simplicity only
            # In production, use a safe math parser or LLM tool
            result = str(eval(user_input))
            response_text = f"The result is: {result}"
        except Exception as e:
            response_text = f"Could not calculate: {user_input}. Error: {e}"

        # Create response parts
        parts = [Part(root=TextPart(text=response_text))]
        
        # Complete the task
        # We send a 'completed_task' event which includes the result artifact
        await event_queue.enqueue_event(
            completed_task(
                context.task_id,
                context.context_id,
                [new_artifact(parts, f"calc_result_{context.task_id}")],
                [context.message],
            )
        )

    async def cancel(self, request: RequestContext, event_queue: EventQueue) -> Task | None:
        print("[Executor] Cancellation requested")
        return None

# --- 2. Main Entry Point ---
def main():
    host = "127.0.0.1"
    port = 8000
    base_url = f"http://{host}:{port}/"
    
    # Define Capabilities
    capabilities = AgentCapabilities(streaming=True)
    skill = AgentSkill(
        id="calculator",
        name="Simple Calculator",
        description="Performs basic arithmetic operations",
        examples=["1 + 1", "5 * 10"]
    )
    
    # Create Agent Card
    agent_card = AgentCard(
        name="demo_calculator_agent",
        description="A demonstration A2A agent that calculates math.",
        url=base_url,
        version="0.1.0",
        defaultInputModes=[ContentTypes.TEXT],
        defaultOutputModes=[ContentTypes.TEXT],
        capabilities=capabilities,
        skills=[skill],
    )
    
    # Setup Server
    handler = DefaultRequestHandler(
        agent_executor=CalculatorExecutor(),
        task_store=InMemoryTaskStore(),
    )
    
    app = A2AStarletteApplication(agent_card=agent_card, http_handler=handler)
    
    print(f"Starting A2A Agent on {base_url}")
    print(f"Agent Card available at {base_url}agent.json")
    
    uvicorn.run(app.build(), host=host, port=port)

if __name__ == "__main__":
    main()
