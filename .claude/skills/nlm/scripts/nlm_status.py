#!/usr/bin/env python3
"""
NLM Second Brain Status — 전체 노트북 현황 조회

Usage: python3 .claude/skills/nlm/scripts/nlm_status.py [--notes]
  --notes: 각 노트북의 Note 목록도 함께 표시
"""

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
NOTEBOOKS_FILE = PROJECT_ROOT / "data" / "nlm-notebooks.json"
NLM_BIN = "nlm"


def run_nlm(args: list[str], timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            [NLM_BIN] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout.strip()
    except FileNotFoundError:
        print("ERROR: nlm CLI not found. Install: npm i -g notebooklm-mcp-cli")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        return ""


def load_notebooks() -> dict:
    if not NOTEBOOKS_FILE.exists():
        print(f"ERROR: {NOTEBOOKS_FILE} not found")
        sys.exit(1)
    with open(NOTEBOOKS_FILE) as f:
        return json.load(f)


def main():
    show_notes = "--notes" in sys.argv

    notebooks = load_notebooks()
    print("=" * 70)
    print("  NLM SECOND BRAIN STATUS")
    print("=" * 70)
    print(f"  Notebooks: {len(notebooks)}")
    print(f"  Registry:  {NOTEBOOKS_FILE}")
    print()

    for agent_name, info in notebooks.items():
        nb_id = info["notebookId"]
        title = info.get("title", "")
        created = info.get("createdAt", "")[:10]

        # Count sources
        src_raw = run_nlm(["source", "list", nb_id, "--json"])
        try:
            sources = json.loads(src_raw) if src_raw else []
        except json.JSONDecodeError:
            sources = []

        # Count notes
        note_raw = run_nlm(["note", "list", nb_id, "--json"])
        try:
            parsed = json.loads(note_raw) if note_raw else {}
            notes = parsed.get("notes", []) if isinstance(parsed, dict) else parsed
        except json.JSONDecodeError:
            notes = []

        print(f"  [{agent_name}]")
        print(f"    ID:      {nb_id}")
        print(f"    Created: {created}")
        print(f"    Sources: {len(sources)}  |  Notes: {len(notes)}")

        if show_notes and notes:
            for n in notes:
                note_title = n.get("title", "(untitled)")
                print(f"      - {note_title}")

        print()

    print("=" * 70)
    print("  Usage: nlm notebook query <ID> \"your question\"")
    print("=" * 70)


if __name__ == "__main__":
    main()
