/**
 * DecisionExecutor — 승인된 Decision을 플랫폼별 실행 스크립트로 라우팅
 *
 * 흐름: JudgmentCycle.handleApproval(approved=true) → DecisionExecutor.execute(decision)
 *       → Python 스크립트 호출 → Decision 상태 업데이트 (executed/failed)
 */

import { log } from '../utils/logger.js';
import { spawnPython as spawnPythonUtil } from '../utils/spawn-python.js';
import type { StateStore } from '../state-store/index.js';
import type { Gateway } from '../core/gateway.js';
import type { Decision } from '../state-store/types.js';
import type { KnowledgeSync } from '../knowledge/knowledge-sync.js';
import type { KnowledgeManager } from '../knowledge/knowledge-manager.js';

interface ExecutionResult {
  status: 'success' | 'error';
  message: string;
  data?: Record<string, any>;
}

export class DecisionExecutor {
  private knowledgeSync?: KnowledgeSync;
  private km?: KnowledgeManager;

  constructor(
    private stateStore: StateStore,
    private gateway: Gateway,
  ) {}

  setKnowledge(km: KnowledgeManager, knowledgeSync: KnowledgeSync): void {
    this.km = km;
    this.knowledgeSync = knowledgeSync;
  }

  /**
   * 승인된 Decision 실행
   * platform 필드에 따라 적절한 스크립트 호출
   */
  async execute(decision: Decision): Promise<void> {
    log('info', `🚀 Executing decision ${decision.id}: ${decision.action} ${decision.target} on ${decision.platform}`);

    try {
      let result: ExecutionResult;

      if (decision.platform === 'binance_spot' || decision.platform === 'binance_futures') {
        result = await this.executeBinance(decision);
      } else if (decision.platform === 'polymarket') {
        result = await this.executePolymarket(decision);
      } else {
        result = { status: 'error', message: `Unknown platform: ${decision.platform}` };
      }

      if (result.status === 'success') {
        decision.status = 'executed';
        if (result.data) {
          decision.result = {
            executed_at: new Date().toISOString(),
            fill_price: result.data.fill_price || 0,
            fee: result.data.fee || 0,
            pnl: null,
          };
        }
        this.stateStore.recordDecision(decision);
        this.notifyTelegram(
          `✅ 체결 완료: ${decision.action} ${decision.target} $${decision.amount}\n` +
          `${result.message}`,
        );
        log('info', `✅ Decision ${decision.id} executed successfully`);
      } else {
        decision.status = 'rejected';
        this.stateStore.recordDecision(decision);
        this.notifyTelegram(
          `❌ 실행 실패: ${decision.action} ${decision.target}\n` +
          `사유: ${result.message}`,
        );
        log('warn', `❌ Decision ${decision.id} execution failed: ${result.message}`);
      }

      // Write-back: 실행 결과를 에이전트 노트북에 Note로 기록
      this.writeBackDecision(decision);
    } catch (error) {
      decision.status = 'rejected';
      this.stateStore.recordDecision(decision);
      this.notifyTelegram(
        `❌ 실행 오류: ${decision.action} ${decision.target}\n` +
        `${error}`,
      );
      log('error', `❌ Decision ${decision.id} execution error: ${error}`);

      // Write-back: 실행 오류도 기록
      this.writeBackDecision(decision);
    }
  }

  /**
   * Binance 주문 실행
   * execute_order.py: --action BUY/SELL --symbol BTC --amount 50 --account spot/futures
   */
  private async executeBinance(decision: Decision): Promise<ExecutionResult> {
    const accountType = decision.platform === 'binance_futures' ? 'futures' : 'spot';
    const args = [
      '--action', decision.action,
      '--symbol', decision.target,
      '--amount', String(decision.amount),
      '--account', accountType,
    ];
    if (decision.price) {
      args.push('--price', String(decision.price));
    }

    return this.spawnPython('execute_order.py', args);
  }

  /**
   * Polymarket 주문 실행
   * polymarket_client.py 활용
   */
  private async executePolymarket(decision: Decision): Promise<ExecutionResult> {
    const args = [
      '--action', decision.action,
      '--market', decision.target,
      '--amount', String(decision.amount),
    ];
    if (decision.price) {
      args.push('--price', String(decision.price));
    }

    return this.spawnPython('execute_pm_order.py', args);
  }

  /**
   * Python 스크립트 실행 (InvestmentScheduler.spawnPython 패턴 재활용)
   */
  private spawnPython(script: string, args: string[]): Promise<ExecutionResult> {
    return spawnPythonUtil({ script, args, skillDir: 'investment', timeoutMs: 120_000 }).then((result) => ({
      status: result.status,
      message: result.message,
      data: result.data,
    }));
  }

  private writeBackDecision(decision: Decision): void {
    if (this.knowledgeSync && this.km) {
      this.knowledgeSync.syncDecisionOutcome(decision, this.km).catch(() => {});
    }
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
