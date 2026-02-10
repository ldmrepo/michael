/**
 * Investment Service Type Definitions
 */

// === Module 1: Portfolio ===

export interface Holding {
  id: number;
  userId: string;
  exchange: string;
  accountType: 'spot' | 'futures';
  symbol: string;
  quantity: number;
  avgEntryPrice: number | null;
  currentPrice: number | null;
  unrealizedPnl: number | null;
  leverage: number | null;
  liquidationPrice: number | null;
  positionSide: string;
  updatedAt: number;
}

export interface Transaction {
  id: number;
  userId: string;
  exchange: string;
  accountType: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  orderType: string;
  quantity: number;
  price: number;
  fee: number;
  feeAsset: string | null;
  realizedPnl: number | null;
  orderId: string | null;
  source: 'manual' | 'semi-auto' | 'dca' | 'rebalance';
  executedAt: number;
  createdAt: number;
}

export interface Snapshot {
  id: number;
  userId: string;
  date: string;
  totalValueUsd: number;
  spotValueUsd: number | null;
  futuresValueUsd: number | null;
  unrealizedPnlUsd: number | null;
  btcPrice: number | null;
  holdingsJson: string | null;
  createdAt: number;
}

// === Module 2: Research ===

export type ResearchCategory =
  | 'market'
  | 'onchain'
  | 'macro'
  | 'sentiment'
  | 'derivatives'
  | 'news'
  | 'etf';

export interface Research {
  id: number;
  source: string;
  category: ResearchCategory;
  symbol: string | null;
  dataJson: string;
  collectedAt: number;
}

// === Module 3: Analysis ===

export type MarketRegime = 'risk_on' | 'risk_off' | 'neutral' | 'crisis';
export type AnalysisType = 'daily' | 'weekly' | 'ad_hoc';

export interface Analysis {
  id: number;
  userId: string;
  analysisType: AnalysisType;
  marketRegime: MarketRegime | null;
  overallScore: number | null;  // -100 ~ +100
  summary: string;
  detailsJson: string | null;
  recommendationsJson: string | null;
  createdAt: number;
}

// === Module 4: Risk ===

export type AlertSeverity = 'info' | 'warning' | 'critical';

export interface RiskAlert {
  id: number;
  userId: string;
  alertType: string;
  severity: AlertSeverity;
  symbol: string | null;
  message: string;
  dataJson: string | null;
  acknowledged: boolean;
  createdAt: number;
}

export interface RiskThreshold {
  id: number;
  userId: string;
  thresholdType: string;
  symbol: string | null;
  value: number;
  active: boolean;
  createdAt: number;
}

// === Module 5: Execution ===

export type ProposalStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'executed'
  | 'failed'
  | 'expired';

export type ProposalType = 'trade' | 'rebalance' | 'dca' | 'stop_loss';

export interface Proposal {
  id: number;
  userId: string;
  proposalType: ProposalType;
  status: ProposalStatus;
  symbol: string;
  side: 'BUY' | 'SELL';
  accountType: string;
  orderType: string;
  quantity: number;
  price: number | null;
  leverage: number | null;
  stopLoss: number | null;
  takeProfit: number | null;
  rationale: string | null;
  analysisId: number | null;
  telegramMessageId: number | null;
  approvedAt: number | null;
  executedAt: number | null;
  executionResultJson: string | null;
  expiresAt: number | null;
  createdAt: number;
}

export interface DcaSchedule {
  id: number;
  userId: string;
  symbol: string;
  accountType: string;
  amountUsd: number;
  cronExpression: string;
  active: boolean;
  lastExecutedAt: number | null;
  totalInvested: number;
  totalQuantity: number;
  createdAt: number;
}

// === Script Output Format ===

export interface ScriptOutput {
  status: 'success' | 'error';
  message: string;
  timestamp: number;
  data?: any;
  alerts?: Array<{
    type: string;
    severity: AlertSeverity;
    symbol?: string;
    message: string;
    data?: any;
  }>;
  report?: string;
  code?: string;
}

// === Scheduler Job ===

export interface InvestmentJob {
  name: string;
  cron: string;
  script: string;
  args?: string[];
  enabled: boolean;
}
