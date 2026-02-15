/**
 * RoutineAgents — 루틴별 전문가 소집 매핑
 *
 * 각 루틴(morning/midday/evening/weekly/monthly)에서
 * 어떤 에이전트(스크립트)를 소집할지 정의한다.
 *
 * 마이클은 판단 전 Gather Phase에서 이 매핑을 참조하여
 * 필요한 전문가만 선택적으로 소집한다.
 */

import type { RoutineType } from './judgment-prompt.js';

export interface GatherEntry {
  agentId: string;               // AGENT_REGISTRY의 키
  scriptIndex?: number;          // tools[] 중 몇 번째 (default: 0)
  args?: string[];               // 추가 인자
}

/**
 * 루틴별 소집 매핑
 *
 * - morning:  풀 소집 — 밤새 변화 전체 파악
 * - midday:   경량 — 포트폴리오 + 가격 + 리스크만
 * - evening:  마감 — 포트폴리오 + 시장 + 뉴스 + 리스크
 * - weekly:   심층 — 전체 수집 + 온체인
 * - monthly:  성과 — 전체 + NAV 스냅샷
 */
export const ROUTINE_AGENTS: Record<RoutineType, GatherEntry[]> = {

  morning: [
    { agentId: 'portfolio' },                       // sync_balance.py
    { agentId: 'market_data' },                     // collect_market.py
    { agentId: 'market_data', scriptIndex: 1 },     // collect_binance_api.py
    { agentId: 'macro' },                           // collect_macro.py
    { agentId: 'news' },                            // collect_news.py
    { agentId: 'pm_scanner' },                      // scan_markets.py
    { agentId: 'risk' },                            // monitor_risk.py
    { agentId: 'social' },                           // scan_influencers.py
  ],

  midday: [
    { agentId: 'portfolio' },                       // sync_balance.py
    { agentId: 'market_data', scriptIndex: 1 },     // collect_binance_api.py
    { agentId: 'risk' },                            // monitor_risk.py
  ],

  evening: [
    { agentId: 'portfolio' },                       // sync_balance.py
    { agentId: 'market_data' },                     // collect_market.py
    { agentId: 'news' },                            // collect_news.py
    { agentId: 'risk' },                            // monitor_risk.py
  ],

  weekly: [
    { agentId: 'portfolio' },                       // sync_balance.py
    { agentId: 'market_data' },                     // collect_market.py
    { agentId: 'market_data', scriptIndex: 1 },     // collect_binance_api.py
    { agentId: 'macro' },                           // collect_macro.py
    { agentId: 'news' },                            // collect_news.py
    { agentId: 'onchain' },                         // collect_etf_flows.py
    { agentId: 'onchain', scriptIndex: 1 },         // collect_smart_money.py
    { agentId: 'onchain', scriptIndex: 2 },         // collect_options.py
    { agentId: 'pm_scanner' },                      // scan_markets.py
    { agentId: 'risk' },                            // monitor_risk.py
    { agentId: 'social', scriptIndex: 1 },           // monitor_trending.py
  ],

  monthly: [
    { agentId: 'portfolio' },                       // sync_balance.py
    { agentId: 'portfolio', scriptIndex: 1 },       // snapshot_nav.py
    { agentId: 'market_data' },                     // collect_market.py
    { agentId: 'macro' },                           // collect_macro.py
    { agentId: 'risk' },                            // monitor_risk.py
    { agentId: 'pm_scanner' },                      // scan_markets.py
  ],
};
