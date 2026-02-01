/**
 * A2A (Agent-to-Agent) Protocol Module
 *
 * Provides A2A server, client, and orchestration capabilities.
 *
 * @module a2a
 */

// Types
export * from './types.js';

// Agent Card
export { MICHAEL_AGENT_CARD, getMichaelAgentCard, canUseSkill, getSkill } from './agent-card.js';

// Server
export { A2AServer, createA2AServer, type A2AServerConfig, type TaskHandler } from './server.js';

// Client
export { A2AClient, createA2AClient, type A2AClientConfig } from './client.js';

// Orchestrator
export {
  A2AOrchestrator,
  createOrchestrator,
  type OrchestratorConfig,
  type RegisteredAgent,
  type MultiAgentTask,
  type TaskStep,
} from './orchestrator.js';
