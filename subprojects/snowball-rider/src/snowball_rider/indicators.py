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


def bb_width_ratio(closes: list[float], period: int = 20) -> list[float | None]:
    """Bollinger Band width / its own SMA. >1.8 = volatility regime shift."""
    results: list[float | None] = []
    for i in range(len(closes)):
        if i + 1 < period:
            results.append(None)
            continue
        window = closes[i + 1 - period : i + 1]
        sma = sum(window) / period
        std = (sum((v - sma) ** 2 for v in window) / period) ** 0.5
        width = (2 * std * 2) / sma if sma > 0 else 0  # (upper - lower) / middle
        results.append(width)
    # Now compute ratio: width / SMA(width, period)
    ratios: list[float | None] = []
    for i in range(len(results)):
        if results[i] is None or i + 1 < period * 2:
            ratios.append(None)
            continue
        recent = [r for r in results[i + 1 - period : i + 1] if r is not None]
        if len(recent) < period:
            ratios.append(None)
        else:
            avg = sum(recent) / len(recent)
            ratios.append(results[i] / avg if avg > 0 else None)
    return ratios


def rolling_min(values: list[float], window: int) -> list[float | None]:
    return [
        min(values[i + 1 - window : i + 1]) if i + 1 >= window else None
        for i in range(len(values))
    ]
