/**
 * Analysis Engine - aggregates research, invokes Claude for analysis,
 * stores results, and formats Telegram reports
 */

import { spawn } from 'child_process';
import { log } from '../utils/logger.js';
import { PortfolioStore } from './portfolio-store.js';
import { InvestmentScheduler } from './scheduler-jobs.js';
import type { Analysis, AnalysisType, ScriptOutput } from './types.js';

type SendReportFn = (userId: string, text: string, buttons?: Array<{ text: string; data: string }>) => void;

export class AnalysisEngine {
  private store: PortfolioStore;
  private scheduler: InvestmentScheduler;
  private sendReport?: SendReportFn;

  constructor(store: PortfolioStore, scheduler: InvestmentScheduler) {
    this.store = store;
    this.scheduler = scheduler;
  }

  /**
   * Set callback for sending reports to Telegram
   */
  setSendReport(fn: SendReportFn): void {
    this.sendReport = fn;
  }

  /**
   * Run analysis: aggregate data via Python → send to Claude via Gateway
   */
  async runAnalysis(userId: string, type: AnalysisType = 'daily'): Promise<ScriptOutput> {
    log('info', `📊 Running ${type} analysis for ${userId}`);

    const args = type === 'weekly' ? ['--weekly'] : ['--daily'];
    args.push('--user-id', userId);

    const output = await this.scheduler.spawnPython('analyze.py', args, `${type}_analysis`);

    if (output.status === 'success' && output.report) {
      try {
        const reportData = JSON.parse(output.report);

        // Build raw data summary first (fallback)
        const rawSummary = this.formatBriefSummary(reportData, type);

        // Attempt Claude AI analysis
        let summary = rawSummary;
        let marketRegime: string | undefined;
        let overallScore: number | undefined;
        let recommendations: string | undefined;

        try {
          const claudeResult = await this.analyzeWithClaude(reportData, type);
          if (claudeResult) {
            summary = claudeResult.summary;
            marketRegime = claudeResult.marketRegime;
            overallScore = claudeResult.overallScore;
            recommendations = claudeResult.recommendations;
          }
        } catch (e) {
          log('warn', `⚠️ Claude analysis failed, using raw summary: ${e}`);
        }

        // Store analysis with Claude-generated fields
        const analysisId = this.store.insertAnalysis(
          userId, type, summary,
          marketRegime, overallScore,
          output.report, recommendations,
        );

        // Send Telegram report
        if (this.sendReport) {
          const buttons = [
            { text: '상세', data: `inv_analysis_detail:id=${analysisId}` },
            { text: '포트폴리오', data: 'inv_portfolio' },
            { text: '알림설정', data: 'inv_risk_settings' },
          ];
          this.sendReport(userId, summary, buttons);
        }

        log('info', `✅ ${type} analysis complete, id=${analysisId}${marketRegime ? `, regime=${marketRegime}` : ''}`);
      } catch (e) {
        log('error', `❌ Failed to process analysis: ${e}`);
      }
    }

    return output;
  }

  /**
   * Invoke Claude CLI for AI-powered market analysis
   */
  private async analyzeWithClaude(
    data: any,
    type: AnalysisType,
  ): Promise<{
    summary: string;
    marketRegime?: string;
    overallScore?: number;
    recommendations?: string;
  } | null> {
    const prompt = this.buildAnalysisPrompt(data, type);

    return new Promise((resolve, reject) => {
      const proc = spawn('claude', ['-p', '--model', 'sonnet'], {
        stdio: ['pipe', 'pipe', 'pipe'],
      });

      let stdout = '';
      let stderr = '';

      proc.stdout?.on('data', (chunk) => { stdout += chunk.toString(); });
      proc.stderr?.on('data', (chunk) => { stderr += chunk.toString(); });

      proc.on('close', (code) => {
        if (code !== 0) {
          reject(new Error(`Claude CLI exited with code ${code}: ${stderr}`));
          return;
        }

        try {
          const result = this.parseClaudeAnalysis(stdout, type);
          resolve(result);
        } catch (e) {
          reject(e);
        }
      });

      proc.on('error', (err) => {
        reject(new Error(`Claude CLI spawn error: ${err.message}`));
      });

      // Send prompt via stdin
      if (proc.stdin) {
        proc.stdin.write(prompt);
        proc.stdin.end();
      }

      // Timeout after 60 seconds
      setTimeout(() => {
        proc.kill();
        reject(new Error('Claude CLI timeout (60s)'));
      }, 60000);
    });
  }

  /**
   * Build the analysis prompt for Claude
   */
  private buildAnalysisPrompt(data: any, type: AnalysisType): string {
    const title = type === 'weekly' ? '주간 투자 분석' : '일일 투자 브리핑';
    const dataJson = JSON.stringify(data, null, 0); // compact

    return `You are an expert cryptocurrency investment analyst. Analyze the following aggregated market data and portfolio information to produce a ${title}.

## Data
\`\`\`json
${dataJson}
\`\`\`

## Instructions
Produce a Korean-language analysis report with the following sections. Use emoji for visual clarity.

1. **시장 국면 판단** (market_regime): One of: risk_on, risk_off, neutral, crisis
   - Based on Fear & Greed, funding rates, price trends, macro indicators

2. **종합 점수** (overall_score): -100 to +100
   - Positive = bullish, Negative = bearish
   - Weight: sentiment(20%), derivatives(20%), onchain(15%), macro(15%), price_action(15%), news(15%)

3. **포트폴리오 요약**: Current holdings, total value, PnL

4. **핵심 인사이트**: 3-5 bullet points about current market conditions

5. **매매 추천** (optional): Only if clear signals exist
   - Symbol, direction (BUY/SELL), rationale, confidence (high/medium/low)

## Output Format
Start your response with a YAML frontmatter block (between --- markers) containing structured data, followed by the full analysis text:

---
market_regime: <risk_on|risk_off|neutral|crisis>
overall_score: <-100 to 100>
recommendations: <JSON array of {symbol, side, rationale, confidence} or empty array []>
---

📊 ${title} (날짜)

(Full analysis text here in Korean...)`;
  }

  /**
   * Parse Claude's analysis response
   */
  private parseClaudeAnalysis(
    response: string,
    _type: AnalysisType,
  ): {
    summary: string;
    marketRegime?: string;
    overallScore?: number;
    recommendations?: string;
  } {
    let marketRegime: string | undefined;
    let overallScore: number | undefined;
    let recommendations: string | undefined;
    let summary = response.trim();

    // Parse YAML frontmatter
    const frontmatterMatch = response.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
    if (frontmatterMatch) {
      const yaml = frontmatterMatch[1];
      summary = frontmatterMatch[2].trim();

      // Extract market_regime
      const regimeMatch = yaml.match(/market_regime:\s*(\S+)/);
      if (regimeMatch) {
        const regime = regimeMatch[1];
        if (['risk_on', 'risk_off', 'neutral', 'crisis'].includes(regime)) {
          marketRegime = regime;
        }
      }

      // Extract overall_score
      const scoreMatch = yaml.match(/overall_score:\s*(-?\d+)/);
      if (scoreMatch) {
        const score = parseInt(scoreMatch[1], 10);
        if (score >= -100 && score <= 100) {
          overallScore = score;
        }
      }

      // Extract recommendations
      const recsMatch = yaml.match(/recommendations:\s*(\[[\s\S]*?\])/);
      if (recsMatch) {
        try {
          const recs = JSON.parse(recsMatch[1]);
          if (Array.isArray(recs) && recs.length > 0) {
            recommendations = JSON.stringify(recs);
          }
        } catch {
          // Invalid JSON, skip
        }
      }
    }

    return { summary, marketRegime, overallScore, recommendations };
  }

  /**
   * Format a brief Telegram-friendly summary from aggregated data
   */
  private formatBriefSummary(data: any, type: AnalysisType): string {
    const now = new Date();
    const dateStr = now.toISOString().split('T')[0];
    const title = type === 'weekly' ? '주간 분석' : '일일 브리핑';

    const portfolio = data.portfolio || [];
    const totalValue = portfolio.reduce((sum: number, h: any) => sum + (h.value_usd || 0), 0);
    const research = data.research || {};

    let report = `📊 ${title} (${dateStr})\n\n`;

    // === Portfolio ===
    if (totalValue > 0) {
      report += `💰 총 자산: $${totalValue.toLocaleString('en-US', { maximumFractionDigits: 0 })}\n`;
      for (const h of portfolio) {
        if (h.value_usd >= 1 && h.symbol !== 'USDT') {
          const pct = ((h.value_usd / totalValue) * 100).toFixed(1);
          let line = `  ${h.symbol} (${h.type}) │ $${h.value_usd.toLocaleString('en-US', { maximumFractionDigits: 0 })} │ ${pct}%`;
          if (h.unrealized_pnl != null) {
            const sign = h.unrealized_pnl >= 0 ? '+' : '';
            line += ` │ PnL ${sign}$${h.unrealized_pnl.toFixed(2)}`;
          }
          report += line + '\n';
        }
      }
      report += '\n';
    }

    // === Sentiment (Fear & Greed) ===
    // F&G data is in research.sentiment (from alternative.me via collect_market)
    const sentimentData = research.sentiment;
    if (sentimentData && Array.isArray(sentimentData)) {
      const fngArr = Array.isArray(sentimentData[0]) ? sentimentData[0] : sentimentData;
      const latest = fngArr[0];
      if (latest?.value != null) {
        const emoji = latest.value <= 20 ? '🔴' : latest.value <= 40 ? '🟠' : latest.value <= 60 ? '🟡' : latest.value <= 80 ? '🟢' : '🔵';
        report += `${emoji} Fear & Greed: ${latest.value} (${latest.classification})\n`;
        // 7-day trend
        if (fngArr.length >= 3) {
          const trend = fngArr.slice(0, 5).map((f: any) => f.value).join(' → ');
          report += `  추이: ${trend}\n`;
        }
      }
    }

    // === Top Coins ===
    const coins = research.coingecko;
    if (Array.isArray(coins) && coins.length > 0) {
      report += '\n📈 주요 코인:\n';
      for (const c of coins.slice(0, 5)) {
        const ch24 = c.change_24h != null ? `${c.change_24h >= 0 ? '+' : ''}${c.change_24h.toFixed(1)}%` : '-';
        const ch7d = c.change_7d != null ? `${c.change_7d >= 0 ? '+' : ''}${c.change_7d.toFixed(1)}%` : '-';
        report += `  ${c.symbol} $${c.price?.toLocaleString('en-US') || '?'} │ 24h ${ch24} │ 7d ${ch7d}\n`;
      }
    }

    // === Derivatives ===
    const derivs = research.derivatives;
    if (Array.isArray(derivs) && derivs.length > 0) {
      report += '\n📉 파생상품:\n';
      for (const d of derivs) {
        if (d.source === 'binance_api' && d.symbol && d.data) {
          const fr = d.data.funding_rate;
          const oi = d.data.open_interest;
          const lsr = d.data.long_short_ratio;
          const parts: string[] = [];
          if (fr && fr.length > 0) {
            const rate = (parseFloat(fr[fr.length - 1].rate) * 100).toFixed(4);
            parts.push(`FR ${rate}%`);
          }
          if (oi) parts.push(`OI ${parseFloat(oi.amount).toLocaleString('en-US', { maximumFractionDigits: 0 })}`);
          if (lsr && lsr.length > 0) parts.push(`L/S ${lsr[lsr.length - 1].ratio}`);
          if (parts.length > 0) {
            report += `  ${d.symbol}: ${parts.join(' │ ')}\n`;
          }
        } else if (d.source === 'options' && d.data) {
          const btcDvol = d.data.btc_dvol;
          const ethDvol = d.data.eth_dvol;
          const parts: string[] = [];
          if (Array.isArray(btcDvol)) parts.push(`BTC DVOL ${btcDvol[4]}`);
          if (Array.isArray(ethDvol)) parts.push(`ETH DVOL ${ethDvol[4]}`);
          if (d.data.btc_index_price) parts.push(`BTC Index $${d.data.btc_index_price.toLocaleString('en-US')}`);
          if (parts.length > 0) {
            report += `  Options: ${parts.join(' │ ')}\n`;
          }
        }
      }
    }

    // === On-chain (DeFi TVL) ===
    const onchain = research.onchain;
    if (Array.isArray(onchain) && onchain.length > 0) {
      const protocols = onchain[0]?.protocols;
      if (Array.isArray(protocols) && protocols.length > 0) {
        report += '\n🔗 DeFi TVL Top 5:\n';
        for (const p of protocols.slice(0, 5)) {
          const tvlB = (p.tvl / 1e9).toFixed(1);
          report += `  ${p.name} │ $${tvlB}B │ ${p.category || '-'}\n`;
        }
      }
    }

    // === Macro ===
    if (research.macro && research.macro.length > 0) {
      const macroItems = research.macro
        .filter((m: any) => m?.series && m?.data?.[0]?.value)
        .map((m: any) => `${m.series}: ${m.data[0].value}`)
        .slice(0, 4);
      if (macroItems.length > 0) {
        report += `\n🏛 매크로: ${macroItems.join(' │ ')}\n`;
      }
    }

    // === News ===
    if (research.news && research.news.length > 0) {
      report += '\n📰 뉴스:\n';
      for (const n of research.news.slice(0, 5)) {
        report += `  • ${n.title?.substring(0, 65) || 'News'}\n`;
      }
    }

    return report;
  }

  /**
   * Get latest analysis
   */
  getLatest(userId: string): Analysis | null {
    return this.store.getLatestAnalysis(userId);
  }
}
