import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { mkdirSync, rmSync, existsSync, writeFileSync } from 'fs';
import { join } from 'path';
import yaml from 'js-yaml';
import { Sentinel } from './index.js';
import type { WatchCheck } from './types.js';

const TEST_DIR = join(process.cwd(), 'data', 'test-sentinel-' + process.pid);

describe('Sentinel', () => {
  let sentinel: Sentinel;

  beforeEach(() => {
    if (existsSync(TEST_DIR)) rmSync(TEST_DIR, { recursive: true });
    mkdirSync(TEST_DIR, { recursive: true });
    // Use invalid URL — we don't want actual WebSocket connections in unit tests
    sentinel = new Sentinel('ws://127.0.0.1:0', TEST_DIR);
  });

  afterEach(async () => {
    await sentinel.stop();
    if (existsSync(TEST_DIR)) rmSync(TEST_DIR, { recursive: true });
  });

  // ─── Evaluation Logic ────────────────────────────────

  describe('evaluate', () => {
    it('triggers CASH_LOW when cash_ratio < min_cash', () => {
      const checks: WatchCheck[] = [{
        name: '현금 부족',
        condition: 'cash_ratio < mandate.min_cash',
        trigger: 'CASH_LOW',
        urgency: 'high',
      }];

      const data = { cash_ratio: 8, min_cash: 10, total_nav: 1000 };
      const triggers = sentinel.evaluate('allocation_watch', checks, data);

      expect(triggers).toHaveLength(1);
      expect(triggers[0].trigger).toBe('CASH_LOW');
      expect(triggers[0].urgency).toBe('high');
    });

    it('does not trigger CASH_LOW when cash is sufficient', () => {
      const checks: WatchCheck[] = [{
        name: '현금 부족',
        condition: 'cash_ratio < mandate.min_cash',
        trigger: 'CASH_LOW',
        urgency: 'high',
      }];

      const data = { cash_ratio: 15, min_cash: 10, total_nav: 1000 };
      const triggers = sentinel.evaluate('allocation_watch', checks, data);

      expect(triggers).toHaveLength(0);
    });

    it('triggers PRICE_CRASH when change_1h >= 10%', () => {
      const checks: WatchCheck[] = [{
        name: '폭락',
        condition: 'abs(change_1h) >= 10%',
        trigger: 'PRICE_CRASH',
        urgency: 'critical',
      }];

      const data = { change_1h: -12.5 };
      const triggers = sentinel.evaluate('price_watch', checks, data);

      expect(triggers).toHaveLength(1);
      expect(triggers[0].trigger).toBe('PRICE_CRASH');
      expect(triggers[0].urgency).toBe('critical');
    });

    it('triggers PRICE_SPIKE when change_1h >= 5%', () => {
      const checks: WatchCheck[] = [{
        name: '급변',
        condition: 'abs(change_1h) >= 5%',
        trigger: 'PRICE_SPIKE',
        urgency: 'high',
      }];

      const data = { change_1h: 7.3 };
      const triggers = sentinel.evaluate('price_watch', checks, data);

      expect(triggers).toHaveLength(1);
      expect(triggers[0].trigger).toBe('PRICE_SPIKE');
    });

    it('does not trigger PRICE_SPIKE when change is small', () => {
      const checks: WatchCheck[] = [{
        name: '급변',
        condition: 'abs(change_1h) >= 5%',
        trigger: 'PRICE_SPIKE',
        urgency: 'high',
      }];

      const data = { change_1h: 2.1 };
      const triggers = sentinel.evaluate('price_watch', checks, data);

      expect(triggers).toHaveLength(0);
    });

    it('triggers LIQUIDATION_NEAR when distance <= 10%', () => {
      const checks: WatchCheck[] = [{
        name: '청산 접근',
        condition: 'distance_to_liquidation <= 10%',
        trigger: 'LIQUIDATION_NEAR',
        urgency: 'critical',
      }];

      const data = { distance_to_liquidation: 5 };
      const triggers = sentinel.evaluate('liquidation_watch', checks, data);

      expect(triggers).toHaveLength(1);
      expect(triggers[0].trigger).toBe('LIQUIDATION_NEAR');
    });

    it('triggers PM_PRICE_MOVE when price_change >= 5%', () => {
      const checks: WatchCheck[] = [{
        name: 'PM 가격 급변',
        condition: 'abs(price_change) >= 5%',
        trigger: 'PM_PRICE_MOVE',
        urgency: 'medium',
      }];

      const data = { price_change: -6 };
      const triggers = sentinel.evaluate('pm_watch', checks, data);

      expect(triggers).toHaveLength(1);
      expect(triggers[0].trigger).toBe('PM_PRICE_MOVE');
    });

    it('triggers PM_EXPIRING when hours_to_expiry <= 24', () => {
      const checks: WatchCheck[] = [{
        name: 'PM 만기 임박',
        condition: 'hours_to_expiry <= 24',
        trigger: 'PM_EXPIRING',
        urgency: 'high',
      }];

      const data = { hours_to_expiry: 12 };
      const triggers = sentinel.evaluate('pm_watch', checks, data);

      expect(triggers).toHaveLength(1);
      expect(triggers[0].trigger).toBe('PM_EXPIRING');
    });

    it('does not trigger without required data fields', () => {
      const checks: WatchCheck[] = [{
        name: '폭락',
        condition: 'abs(change_1h) >= 10%',
        trigger: 'PRICE_CRASH',
        urgency: 'critical',
      }];

      // No change_1h in data
      const triggers = sentinel.evaluate('price_watch', checks, {});
      expect(triggers).toHaveLength(0);
    });
  });

  // ─── Cooldown ────────────────────────────────────────

  describe('cooldown', () => {
    it('prevents duplicate triggers within cooldown period', () => {
      const checks: WatchCheck[] = [{
        name: '현금 부족',
        condition: 'cash_ratio < mandate.min_cash',
        trigger: 'CASH_LOW',
        urgency: 'high',
      }];

      const data = { cash_ratio: 5, min_cash: 10, total_nav: 1000 };

      // First call should trigger
      const first = sentinel.evaluate('allocation_watch', checks, data);
      expect(first).toHaveLength(1);

      // Second call within cooldown should not trigger
      const second = sentinel.evaluate('allocation_watch', checks, data);
      expect(second).toHaveLength(0);
    });
  });

  // ─── Trigger Message Format ──────────────────────────

  describe('trigger message format', () => {
    it('trigger contains required fields', () => {
      const checks: WatchCheck[] = [{
        name: '현금 부족',
        condition: 'cash_ratio < mandate.min_cash',
        trigger: 'CASH_LOW',
        urgency: 'high',
      }];

      const data = { cash_ratio: 5, min_cash: 10, total_nav: 1000 };
      const triggers = sentinel.evaluate('allocation_watch', checks, data);

      expect(triggers[0]).toHaveProperty('trigger', 'CASH_LOW');
      expect(triggers[0]).toHaveProperty('urgency', 'high');
      expect(triggers[0]).toHaveProperty('data');
      expect(triggers[0]).toHaveProperty('timestamp');
      expect(triggers[0].data.category).toBe('allocation_watch');
      expect(triggers[0].data.check_name).toBe('현금 부족');
    });

    it('timestamp is valid ISO string', () => {
      const checks: WatchCheck[] = [{
        name: 'test',
        condition: 'test',
        trigger: 'CASH_LOW',
        urgency: 'high',
      }];

      const triggers = sentinel.evaluate('allocation_watch', checks, {
        cash_ratio: 5, min_cash: 10, total_nav: 1000,
      });

      const ts = new Date(triggers[0].timestamp);
      expect(ts.toISOString()).toBe(triggers[0].timestamp);
    });
  });

  // ─── Start/Stop ──────────────────────────────────────

  describe('lifecycle', () => {
    it('starts without sentinel config and stays inactive', async () => {
      // No mandate.yaml → should not throw
      await sentinel.start();
      // Stop should be safe
      await sentinel.stop();
    });

    it('starts with valid mandate.yaml', async () => {
      const mandate = {
        mandate: {
          return_target: '월 +3~5%',
          max_drawdown: -15,
          risk_first: true,
          max_single_trade: 5,
          max_single_asset: 50,
          min_cash: 10,
          target_allocation: { binance_spot: 35, binance_futures: 15, polymarket: 30, cash: 20 },
        },
        sentinel: {
          allocation_watch: {
            interval: '30m',
            checks: [{
              name: '현금 부족',
              condition: 'cash_ratio < mandate.min_cash',
              trigger: 'CASH_LOW',
              urgency: 'high',
            }],
          },
        },
      };

      writeFileSync(join(TEST_DIR, 'mandate.yaml'), yaml.dump(mandate), 'utf-8');

      await sentinel.start();
      // Give it a moment then stop
      await sentinel.stop();
    });

    it('stop is idempotent', async () => {
      await sentinel.stop();
      await sentinel.stop(); // should not throw
    });
  });
});
