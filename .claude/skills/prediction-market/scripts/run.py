#!/usr/bin/env python3
"""
Universal runner for Prediction Market skill scripts
Ensures all scripts run with the correct virtual environment
"""

import os
import sys
import subprocess
from pathlib import Path


def get_venv_python():
    """Get the virtual environment Python executable"""
    skill_dir = Path(__file__).parent.parent
    venv_dir = skill_dir / ".venv"

    if os.name == 'nt':
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"

    return venv_python


def ensure_venv():
    """Ensure virtual environment exists"""
    skill_dir = Path(__file__).parent.parent
    venv_dir = skill_dir / ".venv"
    setup_script = skill_dir / "scripts" / "setup_environment.py"

    if not venv_dir.exists():
        print("First-time setup: Creating virtual environment...")
        print("  This may take a minute...")

        result = subprocess.run([sys.executable, str(setup_script)])
        if result.returncode != 0:
            print("Failed to set up environment")
            sys.exit(1)

        print("Environment ready!")

    return get_venv_python()


def main():
    """Main runner"""
    if len(sys.argv) < 2:
        print("Usage: python run.py <script_name> [args...]")
        print("\nAvailable scripts:")
        print("  scan_markets.py        - Scan high-probability markets")
        print("  monitor_prices.py      - Monitor price changes")
        print("  monitor_arbitrage.py   - Cross-platform arbitrage detection")
        print("  calculate_kelly.py     - Kelly Criterion position sizing")
        sys.exit(1)

    script_name = sys.argv[1]
    script_args = sys.argv[2:]

    if script_name.startswith('scripts/'):
        script_name = script_name[8:]

    if not script_name.endswith('.py'):
        script_name += '.py'

    skill_dir = Path(__file__).parent.parent
    script_path = skill_dir / "scripts" / script_name

    if not script_path.exists():
        print(f"Script not found: {script_name}")
        print(f"  Looked for: {script_path}")
        sys.exit(1)

    venv_python = ensure_venv()
    cmd = [str(venv_python), str(script_path)] + script_args

    try:
        result = subprocess.run(cmd)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
