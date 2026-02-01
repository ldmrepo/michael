/**
 * Finance Agent Tools
 *
 * API clients for real financial data:
 * - CoinGecko: Cryptocurrency prices (free, no API key)
 * - Yahoo Finance: Stock prices (unofficial, free)
 */

import { log } from '../../utils/logger.js';

// --- Types ---

export interface StockQuote {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
  currency: string;
  market: string;
  high?: number;
  low?: number;
  volume?: number;
  timestamp: string;
}

export interface CryptoQuote {
  id: string;
  symbol: string;
  name: string;
  price: number;
  change24h: number;
  changePercent24h: number;
  marketCap: number;
  volume24h: number;
  currency: string;
  timestamp: string;
}

export interface ExchangeRate {
  from: string;
  to: string;
  rate: number;
  timestamp: string;
}

// --- API Response Types ---

interface CoinGeckoDetailResponse {
  id: string;
  symbol: string;
  name: string;
  market_data: {
    current_price: Record<string, number>;
    price_change_24h_in_currency: Record<string, number>;
    price_change_percentage_24h: number;
    market_cap: Record<string, number>;
    total_volume: Record<string, number>;
  };
}

interface CoinGeckoMarketItem {
  id: string;
  symbol: string;
  name: string;
  current_price: number;
  price_change_24h: number;
  price_change_percentage_24h: number;
  market_cap: number;
  total_volume: number;
}

interface YahooChartMeta {
  symbol?: string;
  regularMarketPrice: number;
  chartPreviousClose?: number;
  previousClose?: number;
  currency: string;
  exchangeName: string;
  shortName?: string;
  longName?: string;
  regularMarketDayHigh?: number;
  regularMarketDayLow?: number;
  regularMarketVolume?: number;
}

interface YahooChartResponse {
  chart?: {
    result?: Array<{
      meta: YahooChartMeta;
      indicators?: {
        quote?: Array<{
          high?: number[];
          low?: number[];
          volume?: number[];
        }>;
      };
    }>;
  };
}

interface ExchangeRateAPIResponse {
  rates?: Record<string, number>;
}

// --- CoinGecko API (Cryptocurrency) ---

const COINGECKO_API = 'https://api.coingecko.com/api/v3';

/**
 * Common cryptocurrency IDs for CoinGecko
 */
const CRYPTO_ID_MAP: Record<string, string> = {
  btc: 'bitcoin',
  bitcoin: 'bitcoin',
  비트코인: 'bitcoin',
  eth: 'ethereum',
  ethereum: 'ethereum',
  이더리움: 'ethereum',
  xrp: 'ripple',
  ripple: 'ripple',
  리플: 'ripple',
  sol: 'solana',
  solana: 'solana',
  솔라나: 'solana',
  doge: 'dogecoin',
  dogecoin: 'dogecoin',
  도지코인: 'dogecoin',
  ada: 'cardano',
  cardano: 'cardano',
  카르다노: 'cardano',
};

/**
 * Get cryptocurrency price from CoinGecko
 */
export async function getCryptoPrice(query: string): Promise<CryptoQuote | null> {
  const coinId = CRYPTO_ID_MAP[query.toLowerCase()] || query.toLowerCase();

  try {
    const url = `${COINGECKO_API}/coins/${coinId}?localization=false&tickers=false&community_data=false&developer_data=false`;

    log('debug', `💰 Fetching crypto price: ${coinId}`);

    const response = await fetch(url);
    if (!response.ok) {
      log('warn', `CoinGecko API error: ${response.status}`);
      return null;
    }

    const data = (await response.json()) as CoinGeckoDetailResponse;

    return {
      id: data.id,
      symbol: data.symbol.toUpperCase(),
      name: data.name,
      price: data.market_data.current_price.krw,
      change24h: data.market_data.price_change_24h_in_currency.krw,
      changePercent24h: data.market_data.price_change_percentage_24h,
      marketCap: data.market_data.market_cap.krw,
      volume24h: data.market_data.total_volume.krw,
      currency: 'KRW',
      timestamp: new Date().toISOString(),
    };
  } catch (error) {
    log('error', `CoinGecko API error: ${error}`);
    return null;
  }
}

/**
 * Get top cryptocurrencies by market cap
 */
export async function getTopCryptos(limit: number = 10): Promise<CryptoQuote[]> {
  try {
    const url = `${COINGECKO_API}/coins/markets?vs_currency=krw&order=market_cap_desc&per_page=${limit}&page=1&sparkline=false`;

    log('debug', `💰 Fetching top ${limit} cryptos`);

    const response = await fetch(url);
    if (!response.ok) {
      log('warn', `CoinGecko API error: ${response.status}`);
      return [];
    }

    const data = (await response.json()) as CoinGeckoMarketItem[];

    return data.map((coin) => ({
      id: coin.id,
      symbol: coin.symbol.toUpperCase(),
      name: coin.name,
      price: coin.current_price,
      change24h: coin.price_change_24h,
      changePercent24h: coin.price_change_percentage_24h,
      marketCap: coin.market_cap,
      volume24h: coin.total_volume,
      currency: 'KRW',
      timestamp: new Date().toISOString(),
    }));
  } catch (error) {
    log('error', `CoinGecko API error: ${error}`);
    return [];
  }
}

// --- Yahoo Finance API (Stocks) ---

const YAHOO_FINANCE_API = 'https://query1.finance.yahoo.com/v8/finance/chart';

/**
 * Common Korean stock symbols for Yahoo Finance
 */
const STOCK_SYMBOL_MAP: Record<string, string> = {
  삼성전자: '005930.KS',
  삼성: '005930.KS',
  sk하이닉스: '000660.KS',
  하이닉스: '000660.KS',
  lg에너지솔루션: '373220.KS',
  현대차: '005380.KS',
  현대자동차: '005380.KS',
  기아: '000270.KS',
  셀트리온: '068270.KS',
  카카오: '035720.KS',
  네이버: '035420.KS',
  naver: '035420.KS',
  posco홀딩스: '005490.KS',
  포스코: '005490.KS',
  삼성sdi: '006400.KS',
  lg화학: '051910.KS',
  // US stocks
  애플: 'AAPL',
  apple: 'AAPL',
  aapl: 'AAPL',
  마이크로소프트: 'MSFT',
  microsoft: 'MSFT',
  msft: 'MSFT',
  구글: 'GOOGL',
  google: 'GOOGL',
  googl: 'GOOGL',
  아마존: 'AMZN',
  amazon: 'AMZN',
  amzn: 'AMZN',
  테슬라: 'TSLA',
  tesla: 'TSLA',
  tsla: 'TSLA',
  엔비디아: 'NVDA',
  nvidia: 'NVDA',
  nvda: 'NVDA',
  메타: 'META',
  meta: 'META',
};

/**
 * Get stock price from Yahoo Finance
 */
export async function getStockPrice(query: string): Promise<StockQuote | null> {
  // Normalize query
  const normalizedQuery = query.toLowerCase().replace(/\s+/g, '');
  let symbol = STOCK_SYMBOL_MAP[normalizedQuery];

  // If not in map, assume it's a direct symbol
  if (!symbol) {
    symbol = query.toUpperCase();
    // Add .KS suffix for Korean stock codes (6 digits)
    if (/^\d{6}$/.test(symbol)) {
      symbol = `${symbol}.KS`;
    }
  }

  try {
    const url = `${YAHOO_FINANCE_API}/${symbol}?interval=1d&range=1d`;

    log('debug', `📈 Fetching stock price: ${symbol}`);

    const response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; MichaelBot/1.0)',
      },
    });

    if (!response.ok) {
      log('warn', `Yahoo Finance API error: ${response.status}`);
      return null;
    }

    const data = (await response.json()) as YahooChartResponse;
    const result = data.chart?.result?.[0];

    if (!result) {
      log('warn', `No data for symbol: ${symbol}`);
      return null;
    }

    const meta = result.meta;
    const quote = result.indicators?.quote?.[0];

    const currentPrice = meta.regularMarketPrice;
    const previousClose = meta.chartPreviousClose ?? meta.previousClose ?? currentPrice;
    const change = currentPrice - previousClose;
    const changePercent = previousClose !== 0 ? (change / previousClose) * 100 : 0;

    // Determine market and currency
    const isKorean = symbol.endsWith('.KS') || symbol.endsWith('.KQ');
    const currency = isKorean ? 'KRW' : meta.currency || 'USD';
    const market = isKorean ? 'KOSPI' : meta.exchangeName || 'NASDAQ';

    return {
      symbol: meta.symbol ?? symbol,
      name: meta.shortName ?? meta.longName ?? symbol,
      price: currentPrice,
      change,
      changePercent,
      currency,
      market,
      high: quote?.high?.[0] || meta.regularMarketDayHigh,
      low: quote?.low?.[0] || meta.regularMarketDayLow,
      volume: quote?.volume?.[0] || meta.regularMarketVolume,
      timestamp: new Date().toISOString(),
    };
  } catch (error) {
    log('error', `Yahoo Finance API error: ${error}`);
    return null;
  }
}

// --- Exchange Rate ---

const EXCHANGE_API = 'https://api.exchangerate-api.com/v4/latest';

/**
 * Get exchange rate
 */
export async function getExchangeRate(
  from: string = 'USD',
  to: string = 'KRW'
): Promise<ExchangeRate | null> {
  try {
    const url = `${EXCHANGE_API}/${from.toUpperCase()}`;

    log('debug', `💱 Fetching exchange rate: ${from} → ${to}`);

    const response = await fetch(url);
    if (!response.ok) {
      log('warn', `Exchange rate API error: ${response.status}`);
      return null;
    }

    const data = (await response.json()) as ExchangeRateAPIResponse;
    const rate = data.rates?.[to.toUpperCase()];

    if (!rate) {
      return null;
    }

    return {
      from: from.toUpperCase(),
      to: to.toUpperCase(),
      rate,
      timestamp: new Date().toISOString(),
    };
  } catch (error) {
    log('error', `Exchange rate API error: ${error}`);
    return null;
  }
}

// --- Utility Functions ---

/**
 * Format currency for display
 */
export function formatCurrency(value: number, currency: string = 'KRW'): string {
  if (currency === 'KRW') {
    return `₩${value.toLocaleString('ko-KR', { maximumFractionDigits: 0 })}`;
  }
  return `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/**
 * Format change with emoji
 */
export function formatChange(change: number, changePercent: number, currency: string = 'KRW'): string {
  const emoji = change >= 0 ? '🔺' : '🔻';
  const sign = change >= 0 ? '+' : '';
  const formattedChange = currency === 'KRW'
    ? `${sign}${change.toLocaleString('ko-KR', { maximumFractionDigits: 0 })}`
    : `${sign}${change.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const formattedPercent = `${sign}${changePercent.toFixed(2)}%`;

  return `${emoji} ${formattedChange} (${formattedPercent})`;
}

/**
 * Format large numbers (volume, market cap)
 */
export function formatLargeNumber(value: number): string {
  if (value >= 1_000_000_000_000) {
    return `${(value / 1_000_000_000_000).toFixed(1)}조`;
  }
  if (value >= 100_000_000) {
    return `${(value / 100_000_000).toFixed(1)}억`;
  }
  if (value >= 10_000) {
    return `${(value / 10_000).toFixed(1)}만`;
  }
  return value.toLocaleString('ko-KR');
}

// --- Detection ---

/**
 * Detect if query is about cryptocurrency
 */
export function isCryptoQuery(query: string): boolean {
  const lowerQuery = query.toLowerCase();
  const cryptoKeywords = [
    'btc', 'bitcoin', '비트코인',
    'eth', 'ethereum', '이더리움',
    'xrp', 'ripple', '리플',
    'sol', 'solana', '솔라나',
    'doge', 'dogecoin', '도지',
    '암호화폐', '코인', 'crypto', 'coin',
  ];
  return cryptoKeywords.some((keyword) => lowerQuery.includes(keyword));
}

/**
 * Detect if query is about stocks
 */
export function isStockQuery(query: string): boolean {
  const lowerQuery = query.toLowerCase();
  const stockKeywords = [
    '주가', '주식', 'stock', '시세',
    '삼성', 'sk', 'lg', '현대', '기아', '카카오', '네이버',
    '애플', 'apple', '테슬라', 'tesla', '엔비디아', 'nvidia',
    '마이크로소프트', 'microsoft', '구글', 'google', '아마존', 'amazon',
    'kospi', '코스피', 'nasdaq', '나스닥',
  ];
  return stockKeywords.some((keyword) => lowerQuery.includes(keyword));
}

/**
 * Extract asset name from query
 */
export function extractAssetName(query: string): string | null {
  const lowerQuery = query.toLowerCase();

  // Check crypto map
  for (const key of Object.keys(CRYPTO_ID_MAP)) {
    if (lowerQuery.includes(key)) {
      return key;
    }
  }

  // Check stock map
  for (const key of Object.keys(STOCK_SYMBOL_MAP)) {
    if (lowerQuery.includes(key)) {
      return key;
    }
  }

  return null;
}
