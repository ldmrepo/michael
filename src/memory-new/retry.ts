/**
 * 간단한 retry 유틸리티
 * Moltbot의 복잡한 retry 로직을 Michael용으로 단순화
 */

export interface RetryOptions {
  attempts: number;
  minDelayMs: number;
  maxDelayMs: number;
  jitter: number;
  shouldRetry?: (err: unknown) => boolean;
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export async function retryAsync<T>(
  fn: () => Promise<T>,
  options: RetryOptions
): Promise<T> {
  const { attempts, minDelayMs, maxDelayMs, jitter, shouldRetry } = options;

  let lastErr: unknown;

  for (let i = 0; i < attempts; i++) {
    try {
      return await fn();
    } catch (err) {
      lastErr = err;

      // 마지막 시도면 에러 throw
      if (i === attempts - 1) {
        break;
      }

      // shouldRetry가 false를 반환하면 즉시 에러 throw
      if (shouldRetry && !shouldRetry(err)) {
        throw err;
      }

      // 지수 백오프 계산
      const baseDelay = minDelayMs * Math.pow(2, i);
      const cappedDelay = Math.min(baseDelay, maxDelayMs);

      // Jitter 추가 (랜덤성으로 충돌 방지)
      const jitterAmount = cappedDelay * jitter * (Math.random() * 2 - 1);
      const delay = Math.max(0, cappedDelay + jitterAmount);

      await sleep(delay);
    }
  }

  throw lastErr ?? new Error("Retry failed");
}
