#!/usr/bin/env python3
"""
Environment Setup for Investment Skill
Manages virtual environment and dependencies automatically
"""

import os
import sys
import subprocess
import venv
from pathlib import Path


class SkillEnvironment:
    """Manages skill-specific virtual environment"""

    def __init__(self):
        self.skill_dir = Path(__file__).parent.parent
        self.venv_dir = self.skill_dir / ".venv"
        self.requirements_file = self.skill_dir / "requirements.txt"

        if os.name == 'nt':
            self.venv_python = self.venv_dir / "Scripts" / "python.exe"
            self.venv_pip = self.venv_dir / "Scripts" / "pip.exe"
        else:
            self.venv_python = self.venv_dir / "bin" / "python"
            self.venv_pip = self.venv_dir / "bin" / "pip"

    def ensure_venv(self) -> bool:
        """Ensure virtual environment exists and is set up"""
        if self.is_in_skill_venv():
            print("✅ Already running in skill virtual environment")
            return True

        if not self.venv_dir.exists():
            print(f"🔧 Creating virtual environment in {self.venv_dir.name}/")
            try:
                venv.create(self.venv_dir, with_pip=True)
                print("✅ Virtual environment created")
            except Exception as e:
                print(f"❌ Failed to create venv: {e}")
                return False

        if self.requirements_file.exists():
            print("📦 Installing dependencies...")
            try:
                subprocess.run(
                    [str(self.venv_pip), "install", "--upgrade", "pip"],
                    check=True, capture_output=True, text=True
                )
                subprocess.run(
                    [str(self.venv_pip), "install", "-r", str(self.requirements_file)],
                    check=True, capture_output=True, text=True
                )
                print("✅ Dependencies installed")

                # Install Chrome for Patchright (browser automation)
                print("🌐 Installing Google Chrome for Patchright...")
                try:
                    subprocess.run(
                        [str(self.venv_python), "-m", "patchright", "install", "chrome"],
                        check=True, capture_output=True, text=True
                    )
                    print("✅ Chrome installed")
                except subprocess.CalledProcessError as e:
                    print(f"⚠️ Warning: Failed to install Chrome: {e}")
                    print("   Run manually: python -m patchright install chrome")

                return True
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to install dependencies: {e}")
                return False
        else:
            print("⚠️ No requirements.txt found")
            return True

    def is_in_skill_venv(self) -> bool:
        """Check if running in the skill's venv"""
        if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
            return Path(sys.prefix) == self.venv_dir
        return False

    def get_python_executable(self) -> str:
        """Get the correct Python executable"""
        if self.venv_python.exists():
            return str(self.venv_python)
        return sys.executable


def main():
    """Main entry point for environment setup"""
    env = SkillEnvironment()
    if env.ensure_venv():
        print(f"\n✅ Environment ready!")
        print(f"   Virtual env: {env.venv_dir}")
        print(f"   Python: {env.get_python_executable()}")
    else:
        print("\n❌ Environment setup failed")
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
