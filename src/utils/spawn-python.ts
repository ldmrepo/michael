/**
 * Shared Python script spawner utility.
 *
 * Extracts the common spawn → stdout/stderr collection → timeout →
 * JSON parsing → safeResolve pattern used across investment, prediction-market,
 * decision-executor, and agent-runner modules.
 */

import { spawn } from 'child_process';
import path from 'path';
import { log } from './logger.js';

export interface SpawnPythonOptions {
  /** Python script name, e.g. 'sync_balance.py' */
  script: string;
  /** Extra CLI arguments passed after the script name */
  args?: string[];
  /** Skill directory key — resolved to `.claude/skills/<skillDir>` */
  skillDir?: 'investment' | 'prediction-market' | 'x';
  /** Timeout in milliseconds (default: 300 000 = 5 min) */
  timeoutMs?: number;
}

export interface SpawnPythonResult {
  status: 'success' | 'error';
  message: string;
  data?: any;
}

const DEFAULT_TIMEOUT = 5 * 60 * 1000; // 5 min

/**
 * Spawn a Python script via `python3 <skillDir>/scripts/run.py <script> [...args]`
 * and return parsed JSON output.
 *
 * JSON parsing: finds the **last** stdout line starting with `{` and JSON.parse()s it.
 * Falls back to raw stdout / stderr on parse failure.
 */
export function spawnPython(options: SpawnPythonOptions): Promise<SpawnPythonResult> {
  const {
    script,
    args = [],
    skillDir = 'investment',
    timeoutMs = DEFAULT_TIMEOUT,
  } = options;

  const cwd = path.resolve(`.claude/skills/${skillDir}`);
  const runPy = path.join(cwd, 'scripts', 'run.py');

  return new Promise((resolve) => {
    const proc = spawn('python3', [runPy, script, ...args], {
      cwd,
      env: { ...process.env },
    });

    let stdout = '';
    let stderr = '';
    let settled = false;

    const safeResolve = (output: SpawnPythonResult) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      resolve(output);
    };

    const timeout = setTimeout(() => {
      proc.kill();
      safeResolve({
        status: 'error',
        message: `Timeout: ${script} exceeded ${timeoutMs / 1000}s`,
      });
    }, timeoutMs);

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

      try {
        const lines = stdout.trim().split('\n');
        const jsonLine = lines.reverse().find(l => l.startsWith('{'));
        if (jsonLine) {
          const parsed = JSON.parse(jsonLine);
          safeResolve({
            status: parsed.status || (code === 0 ? 'success' : 'error'),
            message: parsed.message || 'OK',
            data: parsed,
          });
        } else {
          safeResolve({
            status: code === 0 ? 'success' : 'error',
            message: stdout.substring(0, 500) || 'No JSON output',
          });
        }
      } catch {
        safeResolve({
          status: code === 0 ? 'success' : 'error',
          message: stdout.substring(0, 500) || stderr.substring(0, 500) || 'Parse error',
        });
      }
    });

    proc.on('error', (err) => {
      safeResolve({
        status: 'error',
        message: `Spawn error: ${err.message}`,
      });
    });
  });
}
