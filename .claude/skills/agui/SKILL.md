---
name: agui
description: Comprehensive guide and utilities for building AI agents using the Agent-User Interaction (AG-UI) Protocol. Use when implementing real-time streaming agent applications, frontend/backend tool execution, human-in-the-loop workflows, or web-based AI agent interfaces.
argument-hint: "[implementation: server|client|tools]"
---

# AG-UI Protocol Implementation Guide

This skill provides comprehensive knowledge for building AI agent applications using the **AG-UI (Agent-User Interaction) Protocol**.

> **Reference**: https://learn.microsoft.com/agent-framework/integrations/ag-ui/

---

## Protocol Overview

AG-UI is a standardized protocol for building web-based AI agent applications with real-time streaming, tool execution, and bidirectional communication.

### Key Features

| Feature | Description |
|---------|-------------|
| **Remote Agent Hosting** | Deploy AI agents as web services accessible from multiple clients |
| **Real-time Streaming** | Responses streamed via Server-Sent Events (SSE) |
| **Backend Tools** | Server-side function execution with streamed results |
| **Frontend Tools** | Client-side execution for device-specific operations |
| **Human-in-the-Loop** | Approval workflows for critical operations |
| **Session Management** | Conversation context via thread/session IDs |
| **State Synchronization** | Bidirectional state between client and server |

### Architecture

```
┌─────────────────┐
│  Web Client     │ (Browser, Mobile App)
│  (Frontend)     │
└────────┬────────┘
         │ HTTP POST + SSE Stream
         ▼
┌─────────────────────────┐
│  AG-UI Server           │ (FastAPI/ASP.NET Core)
│  /agent-endpoint        │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  AI Agent               │ (ChatAgent with Tools)
│  + Backend Tools        │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  LLM Provider           │ (Azure OpenAI, OpenAI, etc.)
└─────────────────────────┘
```

---

## Event Types

### Core Protocol Events

| Event Type | Description |
|------------|-------------|
| `RUN_STARTED` | Agent started processing request |
| `RUN_FINISHED` | Agent completed successfully |
| `RUN_ERROR` | Error occurred during execution |
| `TEXT_MESSAGE_START` | Text message begins |
| `TEXT_MESSAGE_CONTENT` | Streamed text delta |
| `TEXT_MESSAGE_END` | Text message ends |
| `TOOL_CALL_START` | Backend tool execution begins |
| `TOOL_CALL_ARGS` | Tool arguments (may stream in chunks) |
| `TOOL_CALL_END` | Tool arguments complete |
| `TOOL_CALL_RESULT` | Backend tool execution result |
| `TOOL_CALL_REQUEST` | Request frontend tool execution |

### Event Format (SSE)

```
data: {"type":"RUN_STARTED","threadId":"abc123","runId":"xyz789"}

data: {"type":"TEXT_MESSAGE_START","messageId":"msg001","role":"assistant"}

data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"msg001","delta":"Hello"}

data: {"type":"TEXT_MESSAGE_END","messageId":"msg001"}

data: {"type":"RUN_FINISHED","threadId":"abc123","runId":"xyz789"}
```

### Naming Conventions

- **Event types**: `UPPERCASE_WITH_UNDERSCORES` (e.g., `RUN_STARTED`)
- **Field names**: `camelCase` (e.g., `threadId`, `runId`, `messageId`)

---

## Installation

### Python (FastAPI)

```bash
pip install agent-framework-ag-ui --pre
```

Installs: `agent-framework-core`, `fastapi`, `uvicorn`

### Environment Variables

```bash
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
export AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4o-mini"
```

---

## Server Implementation

### Basic AG-UI Server

```python
"""AG-UI server with FastAPI."""

import os
from agent_framework import ChatAgent
from agent_framework.azure import AzureOpenAIChatClient
from agent_framework_ag_ui import add_agent_framework_fastapi_endpoint
from azure.identity import AzureCliCredential
from fastapi import FastAPI

# Configuration
endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
deployment_name = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")

if not endpoint or not deployment_name:
    raise ValueError("AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT_NAME required")

# Create chat client
chat_client = AzureOpenAIChatClient(
    credential=AzureCliCredential(),
    endpoint=endpoint,
    deployment_name=deployment_name,
)

# Create agent
agent = ChatAgent(
    name="AGUIAssistant",
    instructions="You are a helpful assistant.",
    chat_client=chat_client,
)

# Create FastAPI app
app = FastAPI(title="AG-UI Server")

# Register AG-UI endpoint
add_agent_framework_fastapi_endpoint(app, agent, "/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8888)
```

### Server with Backend Tools

```python
"""AG-UI server with backend tools."""

import os
from typing import Annotated, Any
from agent_framework import ChatAgent, tool
from agent_framework.azure import AzureOpenAIChatClient
from agent_framework_ag_ui import add_agent_framework_fastapi_endpoint
from azure.identity import AzureCliCredential
from fastapi import FastAPI
from pydantic import Field

# Define backend tools
@tool
def get_weather(
    location: Annotated[str, Field(description="The city name")],
) -> str:
    """Get the current weather for a location."""
    return f"The weather in {location} is sunny with a temperature of 22°C."

@tool
def search_restaurants(
    location: Annotated[str, Field(description="The city to search in")],
    cuisine: Annotated[str, Field(description="Type of cuisine")] = "any",
) -> dict[str, Any]:
    """Search for restaurants in a location."""
    return {
        "location": location,
        "cuisine": cuisine,
        "results": [
            {"name": "The Golden Fork", "rating": 4.5, "price": "$$"},
            {"name": "Bella Italia", "rating": 4.2, "price": "$$$"},
        ],
    }

# Configuration
endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
deployment_name = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")

chat_client = AzureOpenAIChatClient(
    credential=AzureCliCredential(),
    endpoint=endpoint,
    deployment_name=deployment_name,
)

# Create agent with tools
agent = ChatAgent(
    name="TravelAssistant",
    instructions="You are a helpful travel assistant. Use the available tools.",
    chat_client=chat_client,
    tools=[get_weather, search_restaurants],
)

app = FastAPI(title="AG-UI Travel Assistant")
add_agent_framework_fastapi_endpoint(app, agent, "/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8888)
```

### Multiple Agents

```python
app = FastAPI()

weather_agent = ChatAgent(name="weather", ...)
finance_agent = ChatAgent(name="finance", ...)

add_agent_framework_fastapi_endpoint(app, weather_agent, "/weather")
add_agent_framework_fastapi_endpoint(app, finance_agent, "/finance")
```

---

## Client Implementation

### Basic AG-UI Client

```python
"""AG-UI client example."""

import asyncio
import os
from agent_framework import ChatAgent
from agent_framework_ag_ui import AGUIChatClient

async def main():
    server_url = os.environ.get("AGUI_SERVER_URL", "http://127.0.0.1:8888/")
    print(f"Connecting to AG-UI server at: {server_url}\n")

    # Create AG-UI chat client
    chat_client = AGUIChatClient(server_url=server_url)

    # Create agent
    agent = ChatAgent(
        name="ClientAgent",
        chat_client=chat_client,
        instructions="You are a helpful assistant.",
    )

    # Get thread for conversation continuity
    thread = agent.get_new_thread()

    try:
        while True:
            message = input("\nUser (:q to exit): ")
            if not message.strip():
                continue
            if message.lower() in (":q", "quit"):
                break

            print("\nAssistant: ", end="", flush=True)
            async for update in agent.run_stream(message, thread=thread):
                if update.text:
                    print(f"\033[96m{update.text}\033[0m", end="", flush=True)
            print("\n")

    except KeyboardInterrupt:
        print("\n\nExiting...")

if __name__ == "__main__":
    asyncio.run(main())
```

### Client with Tool Event Handling

```python
"""AG-UI client with tool event handling."""

import asyncio
import os
from agent_framework import ChatAgent, ToolCallContent, ToolResultContent
from agent_framework_ag_ui import AGUIChatClient

async def main():
    server_url = os.environ.get("AGUI_SERVER_URL", "http://127.0.0.1:8888/")
    chat_client = AGUIChatClient(server_url=server_url)

    agent = ChatAgent(
        name="ClientAgent",
        chat_client=chat_client,
        instructions="You are a helpful assistant.",
    )

    thread = agent.get_new_thread()

    try:
        while True:
            message = input("\nUser (:q to exit): ")
            if message.lower() in (":q", "quit"):
                break

            print("\nAssistant: ", end="", flush=True)
            async for update in agent.run_stream(message, thread=thread):
                # Display text content
                if update.text:
                    print(f"\033[96m{update.text}\033[0m", end="", flush=True)

                # Display tool calls and results
                for content in update.contents:
                    if isinstance(content, ToolCallContent):
                        print(f"\n\033[95m[Calling: {content.name}]\033[0m")
                    elif isinstance(content, ToolResultContent):
                        result = content.result if isinstance(content.result, str) else str(content.result)
                        print(f"\033[94m[Result: {result}]\033[0m")

            print("\n")

    except KeyboardInterrupt:
        print("\n\nExiting...")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Frontend Tools

Frontend tools execute on the client side, enabling AI agents to interact with local resources.

### Tool Definition

```python
from typing import Annotated
from pydantic import BaseModel, Field

class SensorReading(BaseModel):
    """Sensor reading from client device."""
    temperature: float
    humidity: float
    air_quality_index: int

def read_climate_sensors(
    include_temperature: Annotated[bool, Field(description="Include temperature")] = True,
    include_humidity: Annotated[bool, Field(description="Include humidity")] = True,
) -> SensorReading:
    """Read climate sensor data from the client device."""
    return SensorReading(
        temperature=22.5 if include_temperature else 0.0,
        humidity=45.0 if include_humidity else 0.0,
        air_quality_index=75,
    )

def get_user_location() -> dict:
    """Get the user's current GPS location."""
    return {
        "latitude": 52.3676,
        "longitude": 4.9041,
        "accuracy": 10.0,
        "city": "Amsterdam",
    }
```

### Client with Frontend Tools

```python
"""AG-UI client with frontend tools."""

import asyncio
import json
import os
from typing import Annotated, AsyncIterator
import httpx
from pydantic import BaseModel, Field

class SensorReading(BaseModel):
    temperature: float
    humidity: float
    air_quality_index: int

# Define frontend tools
def read_climate_sensors(
    include_temperature: Annotated[bool, Field(description="Include temperature")] = True,
    include_humidity: Annotated[bool, Field(description="Include humidity")] = True,
) -> SensorReading:
    """Read climate sensor data from the client device."""
    return SensorReading(
        temperature=22.5 if include_temperature else 0.0,
        humidity=45.0 if include_humidity else 0.0,
        air_quality_index=75,
    )

def get_user_location() -> dict:
    """Get the user's current GPS location."""
    return {"latitude": 52.3676, "longitude": 4.9041, "city": "Amsterdam"}

# Tool registry
FRONTEND_TOOLS = {
    "read_climate_sensors": read_climate_sensors,
    "get_user_location": get_user_location,
}

class AGUIClientWithTools:
    """AG-UI client with frontend tool support."""

    def __init__(self, server_url: str, tools: dict):
        self.server_url = server_url
        self.tools = tools
        self.thread_id: str | None = None

    async def send_message(self, message: str) -> AsyncIterator[dict]:
        """Send message and handle streaming response with tool execution."""
        # Prepare tool declarations
        tool_declarations = [
            {"name": name, "description": func.__doc__ or ""}
            for name, func in self.tools.items()
        ]

        request_data = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant with client tools."},
                {"role": "user", "content": message},
            ],
            "tools": tool_declarations,
        }

        if self.thread_id:
            request_data["thread_id"] = self.thread_id

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                self.server_url,
                json=request_data,
                headers={"Accept": "text/event-stream"},
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            event = json.loads(line[6:])

                            # Handle frontend tool call requests
                            if event.get("type") == "TOOL_CALL_REQUEST":
                                await self._handle_tool_call(event, client)
                            else:
                                yield event

                            # Capture thread_id
                            if event.get("type") == "RUN_STARTED" and not self.thread_id:
                                self.thread_id = event.get("threadId")

                        except json.JSONDecodeError:
                            continue

    async def _handle_tool_call(self, event: dict, client: httpx.AsyncClient):
        """Execute frontend tool and send result back."""
        tool_name = event.get("toolName")
        tool_call_id = event.get("toolCallId")
        arguments = event.get("arguments", {})

        print(f"\n\033[95m[Client Tool: {tool_name}]\033[0m")

        try:
            tool_func = self.tools.get(tool_name)
            if not tool_func:
                raise ValueError(f"Unknown tool: {tool_name}")

            result = tool_func(**arguments)

            # Convert Pydantic models to dict
            if hasattr(result, "model_dump"):
                result = result.model_dump()

            print(f"\033[94m[Result: {result}]\033[0m")

            # Send result back to server
            await client.post(
                f"{self.server_url}/tool_result",
                json={"tool_call_id": tool_call_id, "result": result},
            )

        except Exception as e:
            await client.post(
                f"{self.server_url}/tool_result",
                json={"tool_call_id": tool_call_id, "error": str(e)},
            )

async def main():
    server_url = os.environ.get("AGUI_SERVER_URL", "http://127.0.0.1:8888/")
    client = AGUIClientWithTools(server_url, FRONTEND_TOOLS)

    while True:
        message = input("\nUser (:q to exit): ")
        if message.lower() in (":q", "quit"):
            break

        async for event in client.send_message(message):
            event_type = event.get("type", "")
            if event_type == "TEXT_MESSAGE_CONTENT":
                print(f"\033[96m{event.get('delta', '')}\033[0m", end="", flush=True)
            elif event_type == "RUN_FINISHED":
                print(f"\n\033[92m[Done]\033[0m")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Tool Execution Events

### Backend Tool Event Sequence

```json
// 1. Tool call starts
{"type": "TOOL_CALL_START", "toolCallId": "call_abc123", "toolCallName": "get_weather"}

// 2. Arguments streamed
{"type": "TOOL_CALL_ARGS", "toolCallId": "call_abc123", "delta": "{\"location\": \"Paris\"}"}

// 3. Arguments complete
{"type": "TOOL_CALL_END", "toolCallId": "call_abc123"}

// 4. Result returned
{"type": "TOOL_CALL_RESULT", "toolCallId": "call_abc123", "content": "Sunny, 22°C"}
```

### Frontend Tool Event Sequence

```json
// 1. Server requests client tool execution
{"type": "TOOL_CALL_REQUEST", "toolCallId": "call_xyz", "toolName": "get_user_location", "arguments": {}}

// 2. Client executes and POSTs result
POST /tool_result
{"tool_call_id": "call_xyz", "result": {"latitude": 52.36, "longitude": 4.90}}
```

---

## Security Considerations

### Trust Boundary Model

```
Untrusted End User
        ↓
(Limited input: text messages only)
        ↓
Trusted Frontend Server (mediates communication)
        ↓
AG-UI Server (Trusted)
```

### Input Validation

```python
# Message validation
def validate_message(message: str) -> str:
    if len(message) > 10000:
        raise ValueError("Message too long")
    # Sanitize for XSS
    return html.escape(message)

# Tool result validation
def validate_tool_result(result: Any) -> Any:
    if isinstance(result, str) and len(result) > 100000:
        raise ValueError("Result too large")
    return result
```

### Sensitive Data Filtering

```python
@tool
def get_user_data(user_id: str) -> dict:
    """Get user data (filtered for security)."""
    data = fetch_user_from_db(user_id)
    # Filter sensitive fields
    return {
        "name": data.get("name"),
        "email": data.get("email"),
        # Exclude: password_hash, api_keys, internal_ids
    }
```

### Security Best Practices

| Practice | Description |
|----------|-------------|
| **Never expose directly** | Use trusted frontend server to mediate |
| **Validate all input** | Message content, tool args, state objects |
| **Filter tool results** | Remove API keys, PII, internal paths |
| **Human-in-the-loop** | Require approval for critical operations |
| **Rate limiting** | Prevent abuse at frontend server |
| **Authentication** | Implement at application layer |

### Threat Vectors

| Vector | Mitigation |
|--------|------------|
| Message injection | Only allow user role messages from untrusted input |
| Tool injection | Maintain allowlist of valid tools |
| State injection | Validate against JSON schema |
| XSS | HTML escape all user content before rendering |

---

## Testing with curl

```bash
curl -N http://127.0.0.1:8888/ \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "messages": [
      {"role": "user", "content": "What is 2 + 2?"}
    ]
  }'
```

---

## Best Practices

### Tool Implementation

```python
@tool
def safe_tool(
    param: Annotated[str, Field(description="Parameter description")],
) -> str:
    """Clear docstring helps agent understand when to use this tool."""
    try:
        result = perform_operation(param)
        return result
    except Exception as e:
        # Don't expose internal errors
        return f"Unable to complete operation: {type(e).__name__}"
```

### Class-Based Tool Organization

```python
class WeatherTools:
    """Collection of weather-related tools."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    @tool
    def get_current_weather(
        self,
        location: Annotated[str, Field(description="The city")],
    ) -> str:
        """Get current weather for a location."""
        return f"Weather in {location}: Sunny, 22°C"

    @tool
    def get_forecast(
        self,
        location: Annotated[str, Field(description="The city")],
        days: Annotated[int, Field(description="Number of days")] = 3,
    ) -> dict:
        """Get weather forecast."""
        return {"location": location, "forecast": [...]}

# Register tools
weather_tools = WeatherTools(api_key="...")
agent = ChatAgent(
    name="WeatherAgent",
    chat_client=chat_client,
    tools=[weather_tools.get_current_weather, weather_tools.get_forecast],
)
```

### Error Handling

```python
async for event in client.send_message(message):
    if event.get("type") == "RUN_ERROR":
        error_msg = event.get("message", "Unknown error")
        print(f"Error: {error_msg}")
        break
```

### CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-domain.com"],
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["*"],
)
```

---

## Comparison: Backend vs Frontend Tools

| Aspect | Backend Tools | Frontend Tools |
|--------|---------------|----------------|
| **Execution** | Server-side | Client-side |
| **Security** | Secure, controlled | Depends on client |
| **Resources** | Server resources | Local device resources |
| **Use Cases** | DB queries, API calls | GPS, sensors, local files |
| **Updates** | Deploy once | Client update required |

---

## References

- **Microsoft AG-UI Docs**: https://learn.microsoft.com/agent-framework/integrations/ag-ui/
- **AG-UI Protocol Spec**: https://docs.ag-ui.com/
- **AG-UI Dojo (Examples)**: https://dojo.ag-ui.com/
- **Agent Framework GitHub**: https://github.com/microsoft/agent-framework
- **CopilotKit Integration**: https://www.copilotkit.ai/
