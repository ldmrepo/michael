/**
 * AgentRegistry — 14개 전문가 에이전트 4요소 정의
 * CONCEPT.md §489-638: 역할 / 지침 / 도구 / 지식
 *
 * 에이전트는 "TypeScript 설정 데이터"다 — 클래스가 아님.
 * 통신 프로토콜: 스크립트 → JSON stdout → StatePopulator → YAML
 */

export interface AgentTool {
  script: string;                // 'collect_market.py'
  skillDir: 'investment' | 'prediction-market' | 'x';
  args?: string[];
  timeout?: number;              // ms, default 300_000 (5분)
}

export interface AgentDefinition {
  id: string;                    // 'market_data', 'macro', ...
  name: string;                  // '시장 데이터 수집가'
  team: 'intelligence' | 'analysis' | 'execution';
  role: string;                  // CONCEPT.md 역할 원문
  instructions: string;          // CONCEPT.md 지침 원문
  tools: AgentTool[];            // 스크립트 목록
  knowledgeDir: string;          // 'knowledge/market-data/'
  outputFormat?: string;         // 기대 출력 형식
}

/**
 * 14개 전문가 에이전트 레지스트리
 */
export const AGENT_REGISTRY: Record<string, AgentDefinition> = {

  // ─── 정보 수집팀 (Intelligence) ─────────────────────

  market_data: {
    id: 'market_data',
    name: '시장 데이터 수집가',
    team: 'intelligence',
    role: '크립토/전통 시장 가격·거래량·파생상품 데이터 수집',
    instructions: '5분 간격 가격 폴링, 변동 1% 이상 시 즉시 보고',
    tools: [
      { script: 'collect_market.py', skillDir: 'investment' },
      { script: 'collect_binance_api.py', skillDir: 'investment' },
    ],
    knowledgeDir: 'knowledge/market-data/',
    outputFormat: '{ symbol, price, change_24h, volume, funding_rate, open_interest }',
  },

  macro: {
    id: 'macro',
    name: '매크로 분석가',
    team: 'intelligence',
    role: '거시경제 지표 수집 및 해석',
    instructions: '일 2회(08:00, 20:00) FRED 데이터 수집, FOMC/CPI 일정 추적',
    tools: [
      { script: 'collect_macro.py', skillDir: 'investment' },
    ],
    knowledgeDir: 'knowledge/macro/',
    outputFormat: '{ fed_rate, dxy, cpi, unemployment, fed_probability }',
  },

  news: {
    id: 'news',
    name: '뉴스 수집가',
    team: 'intelligence',
    role: '투자 관련 뉴스 수집 및 요약',
    instructions: '2시간 간격, 중복 제거, sentiment 분류(positive/negative/neutral)',
    tools: [
      { script: 'collect_news.py', skillDir: 'investment' },
    ],
    knowledgeDir: 'knowledge/news/',
    outputFormat: '{ headline, source, sentiment, relevance_score, summary }',
  },

  social: {
    id: 'social',
    name: '소셜 감시자',
    team: 'intelligence',
    role: 'X/Twitter 키워드 감시, 시장 심리 포착',
    instructions: '마이클 요청 시 수행, 키 인플루언서 목록 유지',
    tools: [
      { script: 'scan_influencers.py', skillDir: 'x' },
      { script: 'monitor_trending.py', skillDir: 'x' },
    ],
    knowledgeDir: 'knowledge/social/',
    outputFormat: '{ keyword, tweet_count, sentiment, key_accounts, trending }',
  },

  onchain: {
    id: 'onchain',
    name: '온체인 분석가',
    team: 'intelligence',
    role: '기관 자금 흐름, 고래 이동, 옵션 데이터 수집',
    instructions: '일 1~2회, ETF 플로우/고래 이동/옵션 데이터 수집',
    tools: [
      { script: 'collect_etf_flows.py', skillDir: 'investment' },
      { script: 'collect_smart_money.py', skillDir: 'investment' },
      { script: 'collect_options.py', skillDir: 'investment' },
      { script: 'collect_defi.py', skillDir: 'investment' },
    ],
    knowledgeDir: 'knowledge/onchain/',
    outputFormat: '{ etf_flow, whale_moves, iv, max_pain, tvl_ranking }',
  },

  pm_scanner: {
    id: 'pm_scanner',
    name: 'PM 스캐너',
    team: 'intelligence',
    role: 'Polymarket 마켓 탐색, 기회 발견',
    instructions: '15분(가격)/4시간(신규)/6시간(고확률), 차익거래 스프레드 3%+ 플래그',
    tools: [
      { script: 'scan_markets.py', skillDir: 'prediction-market', args: ['--high-prob', '--save', '--json'] },
      { script: 'monitor_prices.py', skillDir: 'prediction-market', args: ['--watchlist', '--once', '--json'] },
    ],
    knowledgeDir: 'knowledge/pm-scanner/',
    outputFormat: '{ market_id, question, yes_price, volume, edge, arb_spread }',
  },

  // ─── 분석팀 (Analysis) ─────────────────────────────

  technical: {
    id: 'technical',
    name: '기술 분석가',
    team: 'analysis',
    role: '차트 패턴, 기술적 지표 분석',
    instructions: '시장데이터 수집가의 데이터 기반 분석, 신호 강도(confidence) 필수 포함',
    tools: [
      { script: 'analyze.py', skillDir: 'investment' },
    ],
    knowledgeDir: 'knowledge/technical/',
    outputFormat: '{ rsi, ma_trend, support, resistance, pattern, signal, confidence }',
  },

  risk: {
    id: 'risk',
    name: '리스크 관리자',
    team: 'analysis',
    role: '포트폴리오 위험 평가, 경고 발생',
    instructions: 'mandate.yaml 대조 필수, 위반 시 거래 차단 플래그',
    tools: [
      { script: 'monitor_risk.py', skillDir: 'investment' },
      { script: 'monitor_prices.py', skillDir: 'investment' },
    ],
    knowledgeDir: 'knowledge/risk/',
    outputFormat: '{ alert_type, severity, position, distance_to_liquidation, recommendation }',
  },

  pm_probability: {
    id: 'pm_probability',
    name: 'PM 확률 분석가',
    team: 'analysis',
    role: '예측시장의 실제 확률 추정, 엣지 계산',
    instructions: 'PM 스캐너 데이터 + 뉴스/매크로 맥락으로 추정, Kelly 기준 필수',
    tools: [
      { script: 'estimate_true_probability.py', skillDir: 'prediction-market' },
    ],
    knowledgeDir: 'knowledge/pm-analysis/',
    outputFormat: '{ market, market_price, estimated_prob, edge, kelly_fraction, confidence }',
  },

  portfolio: {
    id: 'portfolio',
    name: '포트폴리오 분석가',
    team: 'analysis',
    role: '전체 자산 현황 파악, 배분 상태 평가',
    instructions: 'Binance+PM+현금 통합 NAV, 목표 배분 대비 편차',
    tools: [
      { script: 'sync_balance.py', skillDir: 'investment' },
      { script: 'snapshot_nav.py', skillDir: 'investment' },
    ],
    knowledgeDir: 'knowledge/portfolio/',
    outputFormat: '{ total_nav, allocation, deviation_from_target, pnl }',
  },

  // ─── 실행팀 (Execution) ─────────────────────────────

  binance_trader: {
    id: 'binance_trader',
    name: 'Binance 트레이더',
    team: 'execution',
    role: 'Binance Spot/Futures 주문 실행',
    instructions: '마이클 지시 + 사용자 승인 후에만 실행, 주문 전 잔고 확인 필수, 슬리피지 0.5% 초과 시 보고',
    tools: [
      { script: 'execute_order.py', skillDir: 'investment' },
    ],
    knowledgeDir: 'knowledge/binance-exec/',
  },

  pm_trader: {
    id: 'pm_trader',
    name: 'PM 트레이더',
    team: 'execution',
    role: 'Polymarket CLOB에서 포지션 매수/매도',
    instructions: '마이클 지시 + 사용자 승인 후에만 실행, POLY_PROXY 서명 사용, best ask+$0.01로 즉시 체결',
    tools: [
      { script: 'polymarket_client.py', skillDir: 'prediction-market' },
    ],
    knowledgeDir: 'knowledge/pm-exec/',
  },

  dca: {
    id: 'dca',
    name: 'DCA 봇',
    team: 'execution',
    role: '정기적 자동 매수 실행',
    instructions: '사전 승인된 규칙 내 자율 실행(L4), 금액/주기/종목 mandate 준수',
    tools: [
      { script: 'execute_dca.py', skillDir: 'investment' },
    ],
    knowledgeDir: 'knowledge/dca/',
  },

  rebalancer: {
    id: 'rebalancer',
    name: '리밸런서',
    team: 'execution',
    role: '목표 자산배분 비율 복원',
    instructions: '마이클 지시 + 사용자 승인 후에만 실행, 편차 5%+ 초과 시에만 트리거, 크로스 플랫폼 실행 순서 준수',
    tools: [
      { script: 'execute_rebalance.py', skillDir: 'investment' },
    ],
    knowledgeDir: 'knowledge/rebalancer/',
  },
};

/**
 * 팀별 에이전트 목록 조회
 */
export function getAgentsByTeam(team: AgentDefinition['team']): AgentDefinition[] {
  return Object.values(AGENT_REGISTRY).filter(a => a.team === team);
}

/**
 * 도구가 있는(실행 가능한) 에이전트만 조회
 */
export function getExecutableAgents(): AgentDefinition[] {
  return Object.values(AGENT_REGISTRY).filter(a => a.tools.length > 0);
}
