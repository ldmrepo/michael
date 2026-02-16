/**
 * Shared Python script spawner utility.
 *
 * Extracts the common spawn → stdout/stderr collection → timeout →
 * JSON parsing → safeResolve pattern used across investment, prediction-market,
 * decision-executor, and agent-runner modules.
 */

import { spawn, ChildProcess } from 'child_process';
import path from 'path';
import { log } from './logger.js';
import { retryAsync } from '../memory-new/retry.js';

export interface SpawnPythonOptions {
  /** Python script name, e.g. 'sync_balance.py' */
  script: string;
  /** Extra CLI arguments passed after the script name */
  args?: string[];
  /** Skill directory key — resolved to `.claude/skills/<skillDir>` */
  skillDir?: 'investment' | 'prediction-market' | 'x';
  /** Timeout in milliseconds (default: 300 000 = 5 min) */
  timeoutMs?: number;
  /** Opt-in retry with exponential backoff */
  retry?: { attempts: number; minDelayMs?: number; maxDelayMs?: number };
}

export interface SpawnPythonResult {
  status: 'success' | 'error';
  message: string;
  data?: any;
}

const DEFAULT_TIMEOUT = 5 * 60 * 1000; // 5 min
const MAX_STDOUT = 5 * 1024 * 1024; // 5 MB

// --- Step 2: Process tracking ---

const activeProcesses = new Set<ChildProcess>();

/** Kill a process group (SIGKILL to entire group started with detached:true) */
function killProcessGroup(proc: ChildProcess): void {
  if (!proc.pid) return;
  try {
    process.kill(-proc.pid, 'SIGKILL');
  } catch {
    try { proc.kill('SIGKILL'); } catch { /* already dead */ }
  }
}

/** Kill all tracked Python child processes. Call from shutdown hooks. */
export function killAllPythonProcesses(): void {
  if (activeProcesses.size === 0) return;
  log('info', `🧹 Killing ${activeProcesses.size} active Python process(es)...`);
  for (const proc of activeProcesses) {
    killProcessGroup(proc);
  }
  activeProcesses.clear();
}

/** Number of currently running Python processes (for diagnostics). */
export function getActivePythonProcessCount(): number {
  return activeProcesses.size;
}

// --- Step 4: Concurrency queue ---

/**
 * Creates a promise-based concurrency queue.
 * Use to serialise browser-based scripts that share a Chrome profile.
 */
export function createSpawnQueue(concurrency = 1) {
  let running = 0;
  const queue: Array<() => void> = [];
  return async function enqueue<T>(fn: () => Promise<T>): Promise<T> {
    if (running >= concurrency) {
      await new Promise<void>((resolve) => queue.push(resolve));
    }
    running++;
    try {
      return await fn();
    } finally {
      running--;
      queue.shift()?.();
    }
  };
}

// --- Step 3: Retry wrapper (public API) ---

class SpawnPythonError extends Error {
  constructor(public result: SpawnPythonResult) {
    super(result.message);
    this.name = 'SpawnPythonError';
  }
}

/**
 * Spawn a Python script via `python3 <skillDir>/scripts/run.py <script> [...args]`
 * and return parsed JSON output.
 *
 * Supports opt-in retry (exponential backoff) via `options.retry`.
 */
export function spawnPython(options: SpawnPythonOptions): Promise<SpawnPythonResult> {
  const { retry, ...rest } = options;
  const attempt = () => spawnPythonOnce(rest);

  if (!retry || retry.attempts <= 1) return attempt();

  return retryAsync(
    async () => {
      const r = await attempt();
      if (r.status === 'error') throw new SpawnPythonError(r);
      return r;
    },
    {
      attempts: retry.attempts,
      minDelayMs: retry.minDelayMs ?? 2000,
      maxDelayMs: retry.maxDelayMs ?? 30000,
      jitter: 0.3,
    },
  ).catch((err) =>
    err instanceof SpawnPythonError
      ? err.result
      : { status: 'error' as const, message: `Retry exhausted: ${err}` },
  );
}

// --- Core implementation (module-private) ---

function spawnPythonOnce(
  options: Omit<SpawnPythonOptions, 'retry'>,
): Promise<SpawnPythonResult> {
  const {
    script,
    args = [],
    skillDir = 'investment',
    timeoutMs = DEFAULT_TIMEOUT,
  } = options;

  const cwd = path.resolve(`.claude/skills/${skillDir}`);
  const runPy = path.join(cwd, 'scripts', 'run.py');

  return new Promise((resolve) => {
    // Step 1: detached:true → new process group for clean SIGKILL
    const proc = spawn('python3', [runPy, script, ...args], {
      cwd,
      env: { ...process.env },
      detached: true,
    });

    // Step 2: track for shutdown
    activeProcesses.add(proc);

    let stdout = '';
    let stderr = '';
    let settled = false;

    const safeResolve = (output: SpawnPythonResult) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      activeProcesses.delete(proc);
      resolve(output);
    };

    // Step 1: timeout kills entire process group
    const timeout = setTimeout(() => {
      killProcessGroup(proc);
      safeResolve({
        status: 'error',
        message: `Timeout: ${script} exceeded ${timeoutMs / 1000}s`,
      });
    }, timeoutMs);

    // Step 5: stdout buffer cap (keep tail — JSON result is always last line)
    proc.stdout.on('data', (data) => {
      stdout += data.toString();
      if (stdout.length > MAX_STDOUT) {
        stdout = stdout.slice(-MAX_STDOUT / 2);
      }
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('close', (code) => {
      if (stderr) {
        log('debug', `⚠️ ${script} stderr: ${stderr.substring(0, 200)}`);
      }

      // Step 6: robust JSON parsing — reverse scan + multi-line fallback
      try {
        const lines = stdout.trim().split('\n');
        let parsed: any = null;

        // Pass 1: single-line JSON (output_format.py style)
        for (let i = lines.length - 1; i >= 0; i--) {
          const line = lines[i].trim();
          if (line.startsWith('{') && line.endsWith('}')) {
            try {
              parsed = JSON.parse(line);
              break;
            } catch {
              continue;
            }
          }
        }

        // Pass 2: multi-line JSON fallback (e.g. json.dumps with indent)
        if (!parsed) {
          const trimmed = stdout.trim();
          // Find last JSON object in stdout (from last '}' back to matching '{')
          const lastBrace = trimmed.lastIndexOf('}');
          if (lastBrace >= 0) {
            // Scan backwards to find the matching opening brace
            let depth = 0;
            for (let i = lastBrace; i >= 0; i--) {
              if (trimmed[i] === '}') depth++;
              if (trimmed[i] === '{') depth--;
              if (depth === 0) {
                try {
                  parsed = JSON.parse(trimmed.substring(i, lastBrace + 1));
                } catch { /* not valid JSON */ }
                break;
              }
            }
          }
        }

        if (parsed) {
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
