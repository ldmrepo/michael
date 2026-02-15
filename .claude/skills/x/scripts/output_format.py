"""
Standard output format for X/Twitter skill scripts
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
