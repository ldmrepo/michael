#!/usr/bin/env python3
"""
NLM Query — 특정 노트북에 자연어 질의

Usage: python3 .claude/skills/nlm/scripts/nlm_query.py <agent_name> "질문"

Examples:
  python3 .claude/skills/nlm/scripts/nlm_query.py michael "최근 학습한 교훈은?"
  python3 .claude/skills/nlm/scripts/nlm_query.py pm_trader "Gamma API 주의사항"
  python3 .claude/skills/nlm/scripts/nlm_query.py binance_trader "선물 value_usd 계산법"
"""

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
NOTEBOOKS_FILE = PROJECT_ROOT / "data" / "nlm-notebooks.json"
NLM_BIN = "nlm"


def load_notebooks() -> dict:
    if not NOTEBOOKS_FILE.exists():
        print(f"ERROR: {NOTEBOOKS_FILE} not found")
        sys.exit(1)
    with open(NOTEBOOKS_FILE) as f:
        return json.load(f)


def main():
    if len(sys.argv) < 3:
        print("Usage: nlm_query.py <agent_name> \"question\"")
        print()
        notebooks = load_notebooks()
        print("Available notebooks:")
        for name in sorted(notebooks.keys()):
            print(f"  - {name}")
        sys.exit(1)

    agent_name = sys.argv[1]
    question = sys.argv[2]

    notebooks = load_notebooks()
    if agent_name not in notebooks:
        print(f"ERROR: notebook '{agent_name}' not found")
        print(f"Available: {', '.join(sorted(notebooks.keys()))}")
        sys.exit(1)

    nb_id = notebooks[agent_name]["notebookId"]
    print(f"Querying [{agent_name}] ({nb_id})...")
    print(f"Q: {question}")
    print("-" * 60)

    try:
        result = subprocess.run(
            [NLM_BIN, "notebook", "query", nb_id, question],
            capture_output=True,
            text=True,
            timeout=60,
        )
        raw = result.stdout.strip()
        try:
            parsed = json.loads(raw)
            answer = parsed.get("value", {}).get("answer", raw)
            print(answer)
        except json.JSONDecodeError:
            print(raw)
    except FileNotFoundError:
        print("ERROR: nlm CLI not found. Install: npm i -g notebooklm-mcp-cli")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("ERROR: Query timed out (60s)")
        sys.exit(1)


if __name__ == "__main__":
    main()
