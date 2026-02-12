/**
 * PM Scheduler Jobs - manages prediction market cron jobs
 * Uses node-cron directly (independent from main Scheduler)
 */

import cron from 'node-cron';
import { spawn } from 'child_process';
import path from 'path';
import { log } from '../utils/logger.js';
import type { PmJob, PmScriptOutput } from './types.js';

const SKILL_DIR = path.resolve('.claude/skills/prediction-market');
const RUN_PY = path.join(SKILL_DIR, 'scripts', 'run.py');

/**
 * Default PM job schedule
 */
export const DEFAULT_PM_JOBS: PmJob[] = [
  // Market scanning
  { name: 'scan_high_prob', cron: '0 */6 * * *', script: 'scan_markets.py', args: ['--high-prob', '--json', '--pages', '2', '--save'], enabled: true },
  { name: 'scan_new_markets', cron: '0 */4 * * *', script: 'scan_markets.py', args: ['--new', '--json'], enabled: true },

  // Price monitoring
  { name: 'monitor_pm_prices', cron: '*/15 * * * *', script: 'monitor_prices.py', args: ['--watchlist', '--once', '--json', '--threshold', '5'], enabled: true },

  // Arbitrage detection
  { name: 'monitor_arb', cron: '0 */2 * * *', script: 'monitor_arbitrage.py', args: ['--once', '--json', '--threshold', '3'], enabled: true },

  // Daily briefing
  { name: 'pm_daily_brief', cron: '0 9 * * *', script: 'daily_brief.py', args: ['--json'], enabled: true },
];

type JobCallback = (jobName: string, output: PmScriptOutput) => void;

export class PmScheduler {
  private jobs: Map<string, cron.ScheduledTask> = new Map();
  private onJobComplete?: JobCallback;

  constructor() {
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
    for (const job of DEFAULT_PM_JOBS) {
      if (!job.enabled) continue;

      if (!cron.validate(job.cron)) {
        log('warn', `⚠️ Invalid cron: ${job.name} = ${job.cron}`);
        continue;
      }

      const task = cron.schedule(job.cron, () => {
        this.runJob(job);
      });

      this.jobs.set(job.name, task);
      log('debug', `⏰ PM job scheduled: ${job.name} [${job.cron}]`);
    }

    log('info', `✅ PM scheduler started: ${this.jobs.size} jobs`);
  }

  /**
   * Stop all jobs
   */
  stop(): void {
    for (const [, task] of this.jobs) {
      task.stop();
    }
    this.jobs.clear();
    log('info', '⏹️ PM scheduler stopped');
  }

  /**
   * Run a specific job manually
   */
  async runJob(job: PmJob): Promise<PmScriptOutput> {
    log('debug', `🏃 Running PM job: ${job.name}`);
    const args = [...(job.args || [])];
    return this.spawnPython(job.script, args, job.name);
  }

  /**
   * Run a job by name
   */
  async runJobByName(name: string): Promise<PmScriptOutput> {
    const job = DEFAULT_PM_JOBS.find(j => j.name === name);
    if (!job) {
      return { status: 'error', message: `Job not found: ${name}`, timestamp: Math.floor(Date.now() / 1000) };
    }
    return this.runJob(job);
  }

  /**
   * Spawn a Python script via run.py and parse stdout JSON
   */
  spawnPython(script: string, args: string[] = [], jobName?: string): Promise<PmScriptOutput> {
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
          log('warn', `⚠️ ${script} stderr: ${stderr.substring(0, 200)}`);
        }

        let output: PmScriptOutput;
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
          log('debug', `✅ PM ${name}: ${output.message}`);
        } else {
          log('warn', `❌ PM ${name}: ${output.message}`);
        }

        if (this.onJobComplete) {
          this.onJobComplete(name, output);
        }

        resolve(output);
      });

      proc.on('error', (err) => {
        const output: PmScriptOutput = {
          status: 'error',
          message: `Spawn error: ${err.message}`,
          timestamp: Math.floor(Date.now() / 1000),
        };
        resolve(output);
      });
    });
  }

  /**
   * Get job status list
   */
  getJobList(): Array<{ name: string; cron: string; enabled: boolean }> {
    return DEFAULT_PM_JOBS.map(j => ({
      name: j.name,
      cron: j.cron,
      enabled: j.enabled,
    }));
  }
}
