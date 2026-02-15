import { describe, it, expect } from 'vitest';
import { existsSync } from 'fs';
import path from 'path';
import { AGENT_REGISTRY, getAgentsByTeam, getExecutableAgents } from './agent-registry.js';
import { ROUTINE_AGENTS } from './routine-agents.js';
import { AgentRunner } from './agent-runner.js';
import type { AgentDefinition } from './agent-registry.js';
import type { GatherResult } from './agent-runner.js';

// ─── Agent Registry Tests ────────────────────────────

describe('AGENT_REGISTRY', () => {
  const agents = Object.values(AGENT_REGISTRY);

  it('defines exactly 14 agents', () => {
    expect(agents.length).toBe(14);
  });

  it('all agents have required fields', () => {
    for (const agent of agents) {
      expect(agent.id).toBeTruthy();
      expect(agent.name).toBeTruthy();
      expect(['intelligence', 'analysis', 'execution']).toContain(agent.team);
      expect(agent.role).toBeTruthy();
      expect(agent.instructions).toBeTruthy();
      expect(agent.knowledgeDir).toBeTruthy();
      expect(Array.isArray(agent.tools)).toBe(true);
    }
  });

  it('agent id matches record key', () => {
    for (const [key, agent] of Object.entries(AGENT_REGISTRY)) {
      expect(agent.id).toBe(key);
    }
  });

  it('has correct team distribution', () => {
    const intelligence = getAgentsByTeam('intelligence');
    const analysis = getAgentsByTeam('analysis');
    const execution = getAgentsByTeam('execution');

    expect(intelligence.length).toBe(6);  // market_data, macro, news, social, onchain, pm_scanner
    expect(analysis.length).toBe(4);      // technical, risk, pm_probability, portfolio
    expect(execution.length).toBe(4);     // binance_trader, pm_trader, dca, rebalancer
  });

  it('social agent has tools (X/Twitter scripts)', () => {
    const social = AGENT_REGISTRY.social;
    expect(social.tools.length).toBe(2);
    expect(social.tools[0].skillDir).toBe('x');
    expect(social.tools[1].skillDir).toBe('x');
  });

  it('all tool scripts reference valid skillDirs', () => {
    for (const agent of agents) {
      for (const tool of agent.tools) {
        expect(['investment', 'prediction-market', 'x']).toContain(tool.skillDir);
      }
    }
  });

  it('investment tool scripts exist on disk', () => {
    const investmentDir = path.resolve('.claude/skills/investment/scripts');

    for (const agent of agents) {
      for (const tool of agent.tools) {
        if (tool.skillDir === 'investment') {
          const scriptPath = path.join(investmentDir, tool.script);
          expect(existsSync(scriptPath), `Missing: ${scriptPath}`).toBe(true);
        }
      }
    }
  });

  it('prediction-market tool scripts exist on disk', () => {
    const pmDir = path.resolve('.claude/skills/prediction-market/scripts');

    for (const agent of agents) {
      for (const tool of agent.tools) {
        if (tool.skillDir === 'prediction-market') {
          const scriptPath = path.join(pmDir, tool.script);
          expect(existsSync(scriptPath), `Missing: ${scriptPath}`).toBe(true);
        }
      }
    }
  });

  it('getExecutableAgents includes social agent', () => {
    const executable = getExecutableAgents();
    const socialIncluded = executable.find(a => a.id === 'social');
    expect(socialIncluded).toBeDefined();
    expect(executable.length).toBe(14); // all 14 agents have tools
  });

  it('x tool scripts exist on disk', () => {
    const xDir = path.resolve('.claude/skills/x/scripts');

    for (const agent of agents) {
      for (const tool of agent.tools) {
        if (tool.skillDir === 'x') {
          const scriptPath = path.join(xDir, tool.script);
          expect(existsSync(scriptPath), `Missing: ${scriptPath}`).toBe(true);
        }
      }
    }
  });
});

// ─── Routine Agents Tests ────────────────────────────

describe('ROUTINE_AGENTS', () => {
  it('defines all 5 routine types', () => {
    expect(Object.keys(ROUTINE_AGENTS).sort()).toEqual(
      ['evening', 'midday', 'monthly', 'morning', 'weekly'],
    );
  });

  it('all agentIds reference valid AGENT_REGISTRY entries', () => {
    for (const [routine, entries] of Object.entries(ROUTINE_AGENTS)) {
      for (const entry of entries) {
        expect(
          AGENT_REGISTRY[entry.agentId],
          `${routine}: agent "${entry.agentId}" not in AGENT_REGISTRY`,
        ).toBeDefined();
      }
    }
  });

  it('all scriptIndex values are within bounds', () => {
    for (const [routine, entries] of Object.entries(ROUTINE_AGENTS)) {
      for (const entry of entries) {
        const agent = AGENT_REGISTRY[entry.agentId];
        const idx = entry.scriptIndex ?? 0;
        expect(
          idx < agent.tools.length,
          `${routine}: ${entry.agentId} scriptIndex ${idx} >= ${agent.tools.length} tools`,
        ).toBe(true);
      }
    }
  });

  it('morning has the most agents (full gathering)', () => {
    expect(ROUTINE_AGENTS.morning.length).toBeGreaterThanOrEqual(
      ROUTINE_AGENTS.midday.length,
    );
  });

  it('midday is the lightest routine', () => {
    for (const [routine, entries] of Object.entries(ROUTINE_AGENTS)) {
      if (routine !== 'midday') {
        expect(
          entries.length,
          `${routine} should have >= midday entries`,
        ).toBeGreaterThanOrEqual(ROUTINE_AGENTS.midday.length);
      }
    }
  });

  it('all routines include portfolio agent', () => {
    for (const [routine, entries] of Object.entries(ROUTINE_AGENTS)) {
      const hasPortfolio = entries.some(e => e.agentId === 'portfolio');
      expect(hasPortfolio, `${routine} missing portfolio`).toBe(true);
    }
  });

  it('weekly includes onchain agents', () => {
    const onchainEntries = ROUTINE_AGENTS.weekly.filter(e => e.agentId === 'onchain');
    expect(onchainEntries.length).toBeGreaterThanOrEqual(2);
  });
});

// ─── AgentRunner.formatGatherSummary Tests ───────────

describe('AgentRunner.formatGatherSummary', () => {
  it('returns empty string for empty results', () => {
    expect(AgentRunner.formatGatherSummary([])).toBe('');
  });

  it('formats success results', () => {
    const results: GatherResult[] = [
      { agentId: 'portfolio', script: 'sync_balance.py', status: 'success', message: 'OK', durationMs: 1500 },
      { agentId: 'market_data', script: 'collect_market.py', status: 'success', message: 'OK', durationMs: 3200 },
    ];

    const summary = AgentRunner.formatGatherSummary(results);
    expect(summary).toContain('2/2 성공');
    expect(summary).toContain('✅');
    expect(summary).toContain('포트폴리오 분석가');
    expect(summary).toContain('시장 데이터 수집가');
  });

  it('formats mixed success/error results', () => {
    const results: GatherResult[] = [
      { agentId: 'portfolio', script: 'sync_balance.py', status: 'success', message: 'OK', durationMs: 1500 },
      { agentId: 'news', script: 'collect_news.py', status: 'error', message: 'API timeout', durationMs: 5000 },
    ];

    const summary = AgentRunner.formatGatherSummary(results);
    expect(summary).toContain('1/2 성공');
    expect(summary).toContain('✅');
    expect(summary).toContain('❌');
    expect(summary).toContain('API timeout');
  });
});
