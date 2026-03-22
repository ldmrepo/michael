"""Technical indicators: EMA, RSI, rolling max/min."""

from __future__ import annotations


def compute_ema(values: list[float], period: int) -> list[float | None]:
    results: list[float | None] = []
    multiplier = 2.0 / (period + 1.0)
    ema_value: float | None = None
    for index, value in enumerate(values):
        if index + 1 < period:
            results.append(None)
            continue
        if ema_value is None:
            ema_value = sum(values[index + 1 - period : index + 1]) / float(period)
        else:
            ema_value = ((value - ema_value) * multiplier) + ema_value
        results.append(ema_value)
    return results


def compute_rsi(closes: list[float], period: int) -> list[float | None]:
    if not closes:
        return []
    deltas = [0.0] + [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]

    results: list[float | None] = []
    for i in range(len(closes)):
        if i + 1 < period:
            results.append(None)
            continue
        avg_gain = sum(gains[i + 1 - period : i + 1]) / period
        avg_loss = sum(losses[i + 1 - period : i + 1]) / period
        if avg_loss <= 0:
            results.append(100.0)
        else:
            rs = avg_gain / avg_loss
            results.append(100.0 - (100.0 / (1.0 + rs)))
    return results


def rolling_max(values: list[float], window: int) -> list[float | None]:
    return [
        max(values[i + 1 - window : i + 1]) if i + 1 >= window else None
        for i in range(len(values))
    ]


def rolling_min(values: list[float], window: int) -> list[float | None]:
    return [
        min(values[i + 1 - window : i + 1]) if i + 1 >= window else None
        for i in range(len(values))
    ]
