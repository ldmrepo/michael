/**
 * Scheduler Jobs - manages investment cron jobs
 * Uses node-cron directly (independent from main Scheduler)
 */

import cron from 'node-cron';
import { spawn } from 'child_process';
import path from 'path';
import { log } from '../utils/logger.js';
import type { InvestmentJob, ScriptOutput } from './types.js';

const SKILL_DIR = path.resolve('.claude/skills/investment');
const RUN_PY = path.join(SKILL_DIR, 'scripts', 'run.py');

/**
 * Default investment job schedule
 */
export const DEFAULT_JOBS: InvestmentJob[] = [
  // Module 1: Portfolio
  { name: 'sync_balance', cron: '*/30 * * * *', script: 'sync_balance.py', enabled: true },
  { name: 'snapshot_nav', cron: '0 0 * * *', script: 'snapshot_nav.py', enabled: true },

  // Module 2: Research - API
  { name: 'collect_market', cron: '0 */6 * * *', script: 'collect_market.py', enabled: true },
  { name: 'collect_binance', cron: '0 */4 * * *', script: 'collect_binance_api.py', enabled: true },
  { name: 'collect_macro', cron: '0 8,20 * * *', script: 'collect_macro.py', enabled: true },
  { name: 'collect_news', cron: '0 */2 * * *', script: 'collect_news.py', enabled: true },
  { name: 'collect_defi', cron: '0 */6 * * *', script: 'collect_defi.py', enabled: true },

  // Module 2: Research - Browser
  { name: 'collect_etf', cron: '0 22 * * 1-5', script: 'collect_etf_flows.py', enabled: true },
  { name: 'collect_smart', cron: '0 */12 * * *', script: 'collect_smart_money.py', enabled: true },
  { name: 'collect_options', cron: '0 */12 * * *', script: 'collect_options.py', enabled: true },

  // Module 4: Risk Monitoring
  { name: 'monitor_price', cron: '*/5 * * * *', script: 'monitor_prices.py', enabled: true },
  { name: 'monitor_risk', cron: '*/15 * * * *', script: 'monitor_risk.py', enabled: true },
];

// Analysis jobs are triggered by the analysis engine, not by cron directly
// But we keep them here for reference/manual triggering
export const ANALYSIS_JOBS: InvestmentJob[] = [
  { name: 'daily_brief', cron: '0 8 * * *', script: 'analyze.py', args: ['--daily'], enabled: true },
  { name: 'weekly_deep', cron: '0 9 * * 1', script: 'analyze.py', args: ['--weekly'], enabled: true },
];

type JobCallback = (jobName: string, output: ScriptOutput) => void;

export class InvestmentScheduler {
  private jobs: Map<string, cron.ScheduledTask> = new Map();
  private userId: string;
  private onJobComplete?: JobCallback;

  constructor(userId: string = 'default') {
    this.userId = userId;
  }

  /**
   * Set callback for when jobs complete
   */
  setJobCallback(callback: JobCallback): void {
    this.onJobComplete = callback;
  }

  /**
   * Start all enabled jobs
   */
  start(): void {
    const allJobs = [...DEFAULT_JOBS, ...ANALYSIS_JOBS];

    for (const job of allJobs) {
      if (!job.enabled) continue;

      if (!cron.validate(job.cron)) {
        log('warn', `⚠️ Invalid cron: ${job.name} = ${job.cron}`);
        continue;
      }

      const task = cron.schedule(job.cron, () => {
        this.runJob(job);
      });

      this.jobs.set(job.name, task);
      log('debug', `⏰ Investment job scheduled: ${job.name} [${job.cron}]`);
    }

    log('info', `✅ Investment scheduler started: ${this.jobs.size} jobs`);
  }

  /**
   * Stop all jobs
   */
  stop(): void {
    for (const [, task] of this.jobs) {
      task.stop();
    }
    this.jobs.clear();
    log('info', '⏹️ Investment scheduler stopped');
  }

  /**
   * Run a specific job manually
   */
  async runJob(job: InvestmentJob): Promise<ScriptOutput> {
    log('debug', `🏃 Running investment job: ${job.name}`);
    const args = ['--user-id', this.userId, ...(job.args || [])];
    return this.spawnPython(job.script, args, job.name);
  }

  /**
   * Run a job by name
   */
  async runJobByName(name: string): Promise<ScriptOutput> {
    const allJobs = [...DEFAULT_JOBS, ...ANALYSIS_JOBS];
    const job = allJobs.find(j => j.name === name);
    if (!job) {
      return { status: 'error', message: `Job not found: ${name}`, timestamp: Date.now() / 1000 };
    }
    return this.runJob(job);
  }

  /**
   * Spawn a Python script via run.py and parse stdout JSON
   */
  spawnPython(script: string, args: string[] = [], jobName?: string): Promise<ScriptOutput> {
    return new Promise((resolve) => {
      const proc = spawn('python3', [RUN_PY, script, ...args], {
        cwd: SKILL_DIR,
        env: { ...process.env },
      });

      let stdout = '';
      let stderr = '';

      proc.stdout.on('data', (data) => {
        stdout += data.toString();
      });

      proc.stderr.on('data', (data) => {
        stderr += data.toString();
      });

      proc.on('close', (code) => {
        if (stderr) {
          log('debug', `⚠️ ${script} stderr: ${stderr.substring(0, 200)}`);
        }

        let output: ScriptOutput;
        try {
          // Find the last line that looks like JSON
          const lines = stdout.trim().split('\n');
          const jsonLine = lines.reverse().find(l => l.startsWith('{'));
          output = jsonLine ? JSON.parse(jsonLine) : {
            status: code === 0 ? 'success' : 'error',
            message: stdout.substring(0, 500) || 'No output',
            timestamp: Math.floor(Date.now() / 1000),
          };
        } catch {
          output = {
            status: code === 0 ? 'success' : 'error',
            message: stdout.substring(0, 500) || stderr.substring(0, 500) || 'Parse error',
            timestamp: Math.floor(Date.now() / 1000),
          };
        }

        const name = jobName || script;
        if (output.status === 'success') {
          log('debug', `✅ ${name}: ${output.message}`);
        } else {
          log('warn', `❌ ${name}: ${output.message}`);
        }

        if (this.onJobComplete) {
          this.onJobComplete(name, output);
        }

        resolve(output);
      });

      proc.on('error', (err) => {
        const output: ScriptOutput = {
          status: 'error',
          message: `Spawn error: ${err.message}`,
          timestamp: Math.floor(Date.now() / 1000),
        };
        resolve(output);
      });
    });
  }

  /**
   * Get job status
   */
  getJobList(): Array<{ name: string; cron: string; enabled: boolean }> {
    const allJobs = [...DEFAULT_JOBS, ...ANALYSIS_JOBS];
    return allJobs.map(j => ({
      name: j.name,
      cron: j.cron,
      enabled: j.enabled,
    }));
  }
}
