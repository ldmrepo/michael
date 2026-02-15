/**
 * JudgmentCycle — 5단계 판단 루프
 * CONCEPT line 164-171: 읽기 → 분석 → 대조 → 판단 → 기록
 */

import { log } from '../utils/logger.js';
import { StateStore } from '../state-store/index.js';
import { buildJudgmentPrompt } from './judgment-prompt.js';
import { DecisionExecutor } from './decision-executor.js';
import { AgentRunner } from './agent-runner.js';
import type { ClaudeCodeAgent } from '../agent/claude-code.js';
import type { Gateway } from '../core/gateway.js';
import type { Decision } from '../state-store/types.js';
import { AGENT_REGISTRY } from './agent-registry.js';
import type { NlmClient } from '../knowledge/nlm-client.js';
import type { KnowledgeManager } from '../knowledge/knowledge-manager.js';
import type { KnowledgeSync } from '../knowledge/knowledge-sync.js';
import type { RoutineType } from './judgment-prompt.js';

export class JudgmentCycle {
  private km: KnowledgeManager | null = null;
  private judgmentNlm: NlmClient | null = null;
  private agentRunner: AgentRunner | null = null;
  private executor: DecisionExecutor;

  constructor(
    private stateStore: StateStore,
    private agent: ClaudeCodeAgent,
    private gateway: Gateway,
  ) {
    this.executor = new DecisionExecutor(stateStore, gateway);
  }

  setKnowledge(km: KnowledgeManager, judgmentNlm: NlmClient, knowledgeSync?: KnowledgeSync): void {
    this.km = km;
    this.judgmentNlm = judgmentNlm;
    if (knowledgeSync) {
      this.executor.setKnowledge(km, knowledgeSync);
    }
  }

  setAgentRunner(runner: AgentRunner): void {
    this.agentRunner = runner;
  }

  /**
   * 판단 사이클 실행
   * 1. 4개 서랍 읽기
   * 2. 프롬프트 빌드 → Agent 호출
   * 3. [DECISION:...] 마커 파싱 → Decision 객체
   * 4. 서랍4에 기록
   * 5. mandate 한도 체크 → 승인 요청 또는 차단
   */
  async runCycle(trigger?: string): Promise<Decision | null> {
    const mandate = this.stateStore.readMandate();
    if (!mandate) {
      log('warn', '⚠️ JudgmentCycle: mandate.yaml not found, skipping');
      return null;
    }

    // trigger에서 routineType 추출
    const routineType: RoutineType | undefined =
      trigger?.includes('weekly') ? 'weekly'
      : trigger?.includes('monthly') ? 'monthly'
      : trigger?.includes('morning') ? 'morning'
      : trigger?.includes('midday') ? 'midday'
      : trigger?.includes('evening') ? 'evening'
      : undefined;

    // ★ Gather Phase: 루틴 트리거일 때만 전문가 소집
    //   Sentinel 트리거(SENTINEL:)는 이미 데이터가 있으므로 스킵
    let gatherSummary = '';
    if (this.agentRunner && routineType && !trigger?.startsWith('SENTINEL:')) {
      try {
        const results = await this.agentRunner.runGatherPhase(routineType);
        gatherSummary = AgentRunner.formatGatherSummary(results);
      } catch (e) {
        log('warn', `⚠️ Gather Phase failed: ${e}`);
        // Gather 실패해도 판단은 계속 — 기존 state/inputs 사용
      }
    }

    // State/Inputs는 Gather 후 갱신된 최신값
    const state = this.stateStore.readState();
    const inputs = this.stateStore.readInputs();
    const recentDecisions = this.stateStore.getRecentDecisions(5);

    // NLM 지식 조회: 에이전트별 노트북 + judgment 노트북
    let nlmContext = '';

    // 에이전트별 NLM query (Gather 참여 에이전트만)
    if (this.km && gatherSummary) {
      try {
        // gatherSummary가 있으면 runGatherPhase 결과가 있었다는 뜻
        // routineType에 해당하는 에이전트 ID 추출
        const { ROUTINE_AGENTS } = await import('./routine-agents.js');
        const entries = routineType ? (ROUTINE_AGENTS[routineType] || []) : [];
        const agentIds = [...new Set(entries.map(e => e.agentId))];
        const agentNlmContext = await this.queryAgentNotebooks(agentIds, {
          gatherSummary, trigger, routineType,
        });
        if (agentNlmContext) nlmContext = agentNlmContext;
      } catch {
        // 에이전트 NLM 실패 시 skip
      }
    }

    // judgment 노트북 query (기존)
    if (this.judgmentNlm) {
      try {
        const judgmentNlmContext = await this.judgmentNlm.query(
          '현재 상황과 유사한 과거 결정 패턴, 주의할 점이 있는가?',
        );
        if (judgmentNlmContext) {
          nlmContext = [nlmContext, judgmentNlmContext].filter(Boolean).join('\n\n---\n\n');
        }
      } catch {
        // NLM 실패 시 skip — 핵심 판단에 영향 없음
      }
    }

    // 프롬프트 빌드
    const prompt = buildJudgmentPrompt(mandate, state, inputs, recentDecisions, trigger, nlmContext, routineType, gatherSummary);

    log('info', `🧠 JudgmentCycle: running${trigger ? ` (trigger: ${trigger.substring(0, 50)})` : ''}`);

    try {
      // Agent 호출
      const response = await this.agent.executeTask(prompt, { model: 'sonnet' });

      // [DECISION:...] 마커 파싱
      const decision = this.parseDecisionMarker(response);

      if (decision) {
        // 서랍4에 기록
        this.stateStore.recordDecision(decision);

        // mandate 한도 체크
        if (decision.action !== 'HOLD') {
          const totalNav = state?.state.total_nav || 0;
          const tradeRatio = totalNav > 0 ? (decision.amount / totalNav) * 100 : 0;

          if (tradeRatio > mandate.mandate.max_single_trade) {
            // 한도 초과 → 거래 차단
            decision.status = 'rejected';
            decision.mandate_check.max_single_trade = `VIOLATION(${tradeRatio.toFixed(1)}% > ${mandate.mandate.max_single_trade}%)`;
            this.stateStore.recordDecision(decision);

            this.notifyTelegram(
              `⛔ 거래 차단: ${decision.action} ${decision.target}\n` +
              `금액 $${decision.amount}은(는) 단일 거래 한도(${mandate.mandate.max_single_trade}%) 초과\n` +
              `사유: ${decision.reason}`,
            );

            log('warn', `⛔ Decision ${decision.id} rejected: exceeds max_single_trade`);
            return decision;
          }

          // 승인 요청 → Telegram (inline keyboard)
          this.requestApproval(decision);
        } else {
          // HOLD — 조용히 기록만
          log('info', `📋 Decision ${decision.id}: HOLD — ${decision.reason}`);
        }

        return decision;
      }

      log('info', '🧠 JudgmentCycle: no decision marker found in response');
      return null;
    } catch (error) {
      log('error', `❌ JudgmentCycle failed: ${error}`);
      return null;
    }
  }

  /**
   * Telegram [승인]/[거절] 콜백 처리
   */
  async handleApproval(decisionId: string, approved: boolean): Promise<void> {
    // 최근 결정에서 해당 ID 찾기
    const recent = this.stateStore.getRecentDecisions(20);
    const decision = recent.find(d => d.id === decisionId);
    if (!decision) {
      log('warn', `⚠️ Decision not found: ${decisionId}`);
      return;
    }

    if (approved) {
      decision.status = 'approved';
      this.stateStore.recordDecision(decision);
      this.notifyTelegram(`✅ 승인됨: ${decision.action} ${decision.target} $${decision.amount}`);
      log('info', `✅ Decision ${decisionId} approved`);

      // Decision→Execution 파이프라인: HOLD이 아닌 승인된 결정 자동 실행
      if (decision.action !== 'HOLD') {
        try {
          await this.executor.execute(decision);
        } catch (e) {
          log('error', `❌ Decision ${decisionId} execution failed: ${e}`);
        }
      }
    } else {
      decision.status = 'rejected';
      this.stateStore.recordDecision(decision);
      this.notifyTelegram(`❌ 거절됨: ${decision.action} ${decision.target}`);
      log('info', `❌ Decision ${decisionId} rejected by user`);
    }
  }

  // ─── Private ─────────────────────────────────────────

  /**
   * 에이전트별 NLM 노트북 병렬 query
   * 아웃라인 + 맥락 기반 동적 query 생성
   */
  private async queryAgentNotebooks(
    agentIds: string[],
    context: { gatherSummary?: string; trigger?: string; routineType?: string } = {},
  ): Promise<string> {
    if (!this.km) return '';
    const results: string[] = [];

    await Promise.allSettled(
      agentIds.map(async (id) => {
        const agent = AGENT_REGISTRY[id];
        if (!agent) return;
        try {
          const client = await this.km!.getClient(id);
          const outline = await this.km!.getOutline(id);

          // 동적 query: 아웃라인 + 맥락 결합
          const queryParts: string[] = [];
          if (outline?.topics?.length) {
            queryParts.push(`노트북 주제: [${outline.topics.join(', ')}]`);
          }
          if (context.trigger) queryParts.push(`트리거: ${context.trigger.substring(0, 200)}`);
          if (context.gatherSummary) queryParts.push(`최신 데이터: ${context.gatherSummary.substring(0, 500)}`);
          queryParts.push(`이 맥락에서 ${agent.name}의 과거 패턴과 교훈은?`);

          const answer = await client.query(queryParts.join('\n'));
          if (answer) results.push(`### ${agent.name}\n${answer}`);
        } catch { /* skip */ }
      }),
    );

    return results.join('\n\n');
  }

  /**
   * [DECISION:action:target:platform:amount:reason:mandate_check_json] 파싱
   */
  parseDecisionMarker(response: string): Decision | null {
    const match = response.match(
      /\[DECISION:([^:]*):([^:]*):([^:]*):([^:]*):([^:]*):(\{[^}]*\})\]/,
    );
    if (!match) return null;

    const [, action, target, platform, amountStr, reason, mandateCheckJson] = match;

    let mandateCheck: Record<string, string> = {};
    try {
      mandateCheck = JSON.parse(mandateCheckJson);
    } catch {
      mandateCheck = { raw: mandateCheckJson };
    }

    const now = new Date();
    const dateStr = now.toISOString().substring(0, 10).replace(/-/g, '');

    // 오늘 결정 수 기반으로 ID 생성
    const todayDecisions = this.stateStore?.getDecisions(now.toISOString().substring(0, 10)) || [];
    const seq = String(todayDecisions.length + 1).padStart(3, '0');

    return {
      id: `D-${dateStr}-${seq}`,
      timestamp: now.toISOString(),
      action: action || 'HOLD',
      target: target || '',
      platform: platform || '',
      amount: parseFloat(amountStr) || 0,
      reason: reason || '',
      inputs_used: [],
      mandate_check: mandateCheck,
      status: 'proposed',
    };
  }

  private requestApproval(decision: Decision): void {
    const text =
      `🧠 *판단 결과*\n\n` +
      `*${decision.action}* ${decision.target} (${decision.platform})\n` +
      `금액: $${decision.amount}\n` +
      `사유: ${decision.reason}\n\n` +
      `승인하시겠습니까?`;

    this.gateway.broadcast({
      from: 'agent',
      to: 'telegram',
      userId: 'system',
      content: text,
      metadata: {
        inline_keyboard: [[
          { text: '✅ 승인', callback_data: `jdg_approve:id=${decision.id}` },
          { text: '❌ 거절', callback_data: `jdg_reject:id=${decision.id}` },
        ]],
      },
    });
  }

  private notifyTelegram(text: string): void {
    this.gateway.broadcast({
      from: 'agent',
      to: 'telegram',
      userId: 'system',
      content: text,
    });
  }
}
