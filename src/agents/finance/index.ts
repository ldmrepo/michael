/**
 * Finance Agent Public Exports
 *
 * Entry point for the Finance Agent module.
 */

// Agent card and skill detection
export {
  createFinanceAgentCard,
  detectSkill,
  matchesSkill,
  FINANCE_SKILLS,
} from './agent.js';

// Agent executor
export {
  FinanceAgentExecutor,
  createFinanceExecutor,
} from './executor.js';

// A2A Server
export {
  FinanceAgentServer,
  startFinanceAgentServer,
  type FinanceServerConfig,
} from './server.js';

// System prompts
export {
  FINANCE_SYSTEM_PROMPT,
  FINANCE_PROMPTS,
} from './prompts.js';
