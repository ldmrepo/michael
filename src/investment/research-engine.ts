/**
 * Research Engine - triggers Python collectors and queries research DB
 */

import { log } from '../utils/logger.js';
import { PortfolioStore } from './portfolio-store.js';
import { InvestmentScheduler } from './scheduler-jobs.js';
import type { Research, ResearchCategory, ScriptOutput } from './types.js';

export class ResearchEngine {
  private store: PortfolioStore;
  private scheduler: InvestmentScheduler;

  constructor(store: PortfolioStore, scheduler: InvestmentScheduler) {
    this.store = store;
    this.scheduler = scheduler;
  }

  /**
   * Run all API collectors now (for ad-hoc refresh)
   */
  async collectAll(): Promise<Record<string, ScriptOutput>> {
    const scripts = [
      'collect_market.py',
      'collect_binance_api.py',
      'collect_news.py',
      'collect_defi.py',
    ];

    const results: Record<string, ScriptOutput> = {};
    for (const script of scripts) {
      const name = script.replace('.py', '');
      try {
        results[name] = await this.scheduler.spawnPython(script, ['--user-id', 'default']);
      } catch (e) {
        log('error', `❌ ${name} failed: ${e}`);
        results[name] = { status: 'error', message: String(e), timestamp: Date.now() / 1000 };
      }
    }
    return results;
  }

  /**
   * Run browser collectors (slower, requires auth)
   */
  async collectBrowser(): Promise<Record<string, ScriptOutput>> {
    const scripts = ['collect_etf_flows.py', 'collect_smart_money.py', 'collect_options.py'];
    const results: Record<string, ScriptOutput> = {};
    for (const script of scripts) {
      const name = script.replace('.py', '');
      try {
        results[name] = await this.scheduler.spawnPython(script);
      } catch (e) {
        log('error', `❌ ${name} failed: ${e}`);
        results[name] = { status: 'error', message: String(e), timestamp: Date.now() / 1000 };
      }
    }
    return results;
  }

  /**
   * Run macro collector
   */
  async collectMacro(): Promise<ScriptOutput> {
    return this.scheduler.spawnPython('collect_macro.py');
  }

  /**
   * Get latest research by category
   */
  getLatest(category?: ResearchCategory, hours = 24): Research[] {
    return this.store.getLatestResearch(category, hours);
  }

  /**
   * Get a summary of available research data
   */
  getResearchSummary(hours = 24): Record<string, number> {
    const categories: ResearchCategory[] = [
      'market', 'onchain', 'macro', 'sentiment', 'derivatives', 'news', 'etf',
    ];

    const summary: Record<string, number> = {};
    for (const cat of categories) {
      summary[cat] = this.store.getLatestResearch(cat, hours).length;
    }
    return summary;
  }
}
