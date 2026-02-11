/**
 * Prediction Market Service Type Definitions
 */

// === Script Output ===

export interface PmScriptOutput {
  status: 'success' | 'error';
  message: string;
  timestamp: number;
  data?: any;
  alerts?: PmAlert[];
  report?: string;
  code?: string;
}

export interface PmAlert {
  type: 'price_change' | 'arbitrage' | 'expiring_market' | 'new_opportunity';
  market_id?: string;
  question?: string;
  direction?: string;
  change_pct?: number;
  current_price?: number;
  prev_price?: number;
  net_profit_pct?: number;
  message?: string;
}

export interface PmJob {
  name: string;
  cron: string;
  script: string;
  args?: string[];
  enabled: boolean;
}

// === DB Row Types (matching pm_* tables) ===

export interface PmMarket {
  id: string;
  question: string;
  slug: string;
  outcomes: string;
  end_date: string;
  tags: string;
  active: number;
  volume: number;
  liquidity: number;
  created_at: number;
  updated_at: number;
}

export interface PmPosition {
  id: number;
  user_id: string;
  market_id: string;
  side: 'YES' | 'NO';
  size: number;
  entry_price: number;
  current_price: number | null;
  status: 'open' | 'closed' | 'settled';
  pnl: number | null;
  opened_at: number;
  closed_at: number | null;
}

export interface PmPrice {
  id: number;
  market_id: string;
  yes_price: number;
  no_price: number;
  volume_24h: number;
  liquidity: number;
  recorded_at: number;
}

export interface PmTrade {
  id: number;
  market_id: string;
  side: string;
  order_type: string;
  price: number;
  size: number;
  fee: number;
  order_id: string;
  executed_at: number;
}

export interface PmAlertRow {
  id: number;
  user_id: string;
  alert_type: string;
  market_id: string | null;
  message: string;
  data_json: string | null;
  acknowledged: number;
  created_at: number;
}
