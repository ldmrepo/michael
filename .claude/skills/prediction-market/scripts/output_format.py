"""
Standard output format for Prediction Market skill scripts
All scripts output JSON to stdout for TypeScript parsing
"""

import json
import sys
import time
from typing import Any, Dict, List, Optional


def success(data: Any = None, message: str = "ok") -> None:
    """Print success result as JSON to stdout"""
    result = {
        "status": "success",
        "message": message,
        "timestamp": int(time.time()),
    }
    if data is not None:
        result["data"] = data
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


def error(message: str, code: str = "ERROR", data: Any = None) -> None:
    """Print error result as JSON to stdout"""
    result = {
        "status": "error",
        "message": message,
        "code": code,
        "timestamp": int(time.time()),
    }
    if data is not None:
        result["data"] = data
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(1)


def alerts(alert_list: List[Dict[str, Any]], message: str = "ok") -> None:
    """Print alerts result (for monitor scripts)"""
    result = {
        "status": "success",
        "message": message,
        "timestamp": int(time.time()),
        "alerts": alert_list,
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


def report(report_text: str, data: Any = None) -> None:
    """Print report result (for analysis scripts)"""
    result = {
        "status": "success",
        "message": "report_generated",
        "timestamp": int(time.time()),
        "report": report_text,
    }
    if data is not None:
        result["data"] = data
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


def table(headers: List[str], rows: List[List[Any]], title: str = "") -> str:
    """Format data as aligned text table"""
    if not rows:
        return "No data"

    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))

    # Build table
    lines = []
    if title:
        lines.append(f"\n{'=' * 60}")
        lines.append(f"  {title}")
        lines.append(f"{'=' * 60}")

    # Header
    header_line = " | ".join(
        str(h).ljust(col_widths[i]) for i, h in enumerate(headers)
    )
    lines.append(header_line)
    lines.append("-+-".join("-" * w for w in col_widths))

    # Rows
    for row in rows:
        row_line = " | ".join(
            str(cell).ljust(col_widths[i]) if i < len(col_widths) else str(cell)
            for i, cell in enumerate(row)
        )
        lines.append(row_line)

    return "\n".join(lines)
