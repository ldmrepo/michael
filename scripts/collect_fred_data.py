#!/usr/bin/env python3
"""
FRED Economic Data Collection Script

Collects key economic indicators from FRED API:
- Federal Funds Rate (FEDFUNDS)
- CPI (CPIAUCSL)
- Unemployment Rate (UNRATE)
- Non-farm Payroll (PAYEMS)
- Real GDP (GDPC1)
- S&P 500 (SP500)
- 10-Year Treasury Yield (DGS10)

Usage:
    python scripts/collect_fred_data.py [--notebook-id NOTEBOOK_ID] [--days DAYS]

Environment:
    FRED_API_KEY: Required FRED API key (https://fred.stlouisfed.org/docs/api/api_key.html)
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests
import subprocess

# FRED API Configuration
FRED_API_KEY = os.environ.get("FRED_API_KEY")
FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# Economic Indicators
INDICATORS = {
    "FEDFUNDS": "Federal Funds Rate (%)",
    "CPIAUCSL": "Consumer Price Index (CPI)",
    "UNRATE": "Unemployment Rate (%)",
    "PAYEMS": "Non-farm Payroll (Thousands)",
    "GDPC1": "Real GDP (Billions $)",
    "SP500": "S&P 500 Index",
    "DGS10": "10-Year Treasury Yield (%)",
}


def fetch_fred_series(series_id: str, days: int = 365) -> List[Dict]:
    """Fetch FRED series data for the last N days."""
    if not FRED_API_KEY:
        raise ValueError("FRED_API_KEY environment variable not set")

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": start_date.strftime("%Y-%m-%d"),
        "observation_end": end_date.strftime("%Y-%m-%d"),
        "sort_order": "desc",  # Most recent first
        "limit": 100,  # Get last 100 observations
    }

    response = requests.get(FRED_BASE_URL, params=params)
    response.raise_for_status()

    data = response.json()
    observations = data.get("observations", [])

    # Filter out "." values (missing data)
    valid_obs = [
        {"date": obs["date"], "value": float(obs["value"])}
        for obs in observations
        if obs["value"] != "."
    ]

    return valid_obs


def format_indicator_data(series_id: str, name: str, data: List[Dict]) -> str:
    """Format indicator data as markdown."""
    if not data:
        return f"*{name}*: No data available\n"

    latest = data[0]  # Most recent (sorted desc)
    prev = data[1] if len(data) > 1 else None

    # Calculate change
    change_str = ""
    if prev:
        change = latest["value"] - prev["value"]
        change_pct = (change / prev["value"]) * 100 if prev["value"] != 0 else 0
        sign = "+" if change >= 0 else ""
        change_str = f" ({sign}{change:.2f}, {sign}{change_pct:.2f}%)"

    # Format based on indicator type
    if series_id in ["FEDFUNDS", "UNRATE", "DGS10"]:
        value_str = f"{latest['value']:.2f}%"
    elif series_id in ["PAYEMS", "GDPC1"]:
        value_str = f"{latest['value']:,.0f}"
    elif series_id == "CPIAUCSL":
        value_str = f"{latest['value']:.1f}"
    else:
        value_str = f"{latest['value']:.2f}"

    return f"*{name}*\n  • Latest ({latest['date']}): {value_str}{change_str}\n"


def collect_all_indicators(days: int = 365) -> str:
    """Collect all FRED indicators and format as markdown."""
    print(f"📊 Collecting FRED data (last {days} days)...")

    results = []
    for series_id, name in INDICATORS.items():
        try:
            print(f"  → Fetching {series_id} ({name})...")
            data = fetch_fred_series(series_id, days)
            formatted = format_indicator_data(series_id, name, data)
            results.append(formatted)
        except Exception as e:
            print(f"  ⚠️  Error fetching {series_id}: {e}")
            results.append(f"*{name}*: Error - {str(e)}\n")

    # Build final report
    header = f"# FRED Economic Indicators Report\n\n"
    header += f"*Generated*: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    header += f"*Period*: Last {days} days\n\n"
    header += "━━━━━━━━━━━━━━━━━━━━\n\n"

    report = header + "\n".join(results)
    return report


def save_to_nlm_notebook(report: str, notebook_id: str):
    """Save report to NLM notebook using nlm note create."""
    title = f"FRED Data - {datetime.now().strftime('%Y-%m-%d')}"

    # Use nlm CLI to create note
    cmd = [
        "nlm",
        "note",
        "create",
        notebook_id,
        "--title",
        title,
        "--content",
        report,
    ]

    print(f"\n💾 Saving to NLM notebook {notebook_id}...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"✅ Note created successfully!")
        print(result.stdout)
    else:
        print(f"❌ Failed to create note:")
        print(result.stderr)
        raise RuntimeError(f"nlm note create failed: {result.stderr}")


def main():
    parser = argparse.ArgumentParser(
        description="Collect FRED economic data and save to NLM"
    )
    parser.add_argument(
        "--notebook-id",
        default="c3cebd51-e260-4de4-9a57-a9cc9913dd4c",
        help="NLM notebook ID (default: michael notebook)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Number of days to collect (default: 365)",
    )
    parser.add_argument(
        "--output",
        help="Save report to file instead of NLM",
    )

    args = parser.parse_args()

    # Collect data
    report = collect_all_indicators(args.days)

    # Save to file or NLM
    if args.output:
        with open(args.output, "w") as f:
            f.write(report)
        print(f"\n✅ Report saved to {args.output}")
    else:
        save_to_nlm_notebook(report, args.notebook_id)

    print("\n━━━━━━━━━━━━━━━━━━━━")
    print("🎉 FRED data collection complete!")
    print("━━━━━━━━━━━━━━━━━━━━\n")


if __name__ == "__main__":
    main()
