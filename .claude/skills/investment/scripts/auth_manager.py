#!/usr/bin/env python3
"""
Authentication Manager for Binance Browser Automation
Handles Binance login and browser state persistence
"""

import json
import time
import argparse
import shutil
import re
import sys
from pathlib import Path
from typing import Dict, Any

from patchright.sync_api import sync_playwright, BrowserContext

sys.path.insert(0, str(Path(__file__).parent))

from config import (
    BROWSER_STATE_DIR, STATE_FILE, AUTH_INFO_FILE, DATA_DIR,
    BINANCE_LOGIN_URL, BINANCE_AUTH_CHECK_SELECTOR
)
from browser_utils import BrowserFactory


class AuthManager:
    """Manages Binance browser authentication and state persistence"""

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        BROWSER_STATE_DIR.mkdir(parents=True, exist_ok=True)
        self.state_file = STATE_FILE
        self.auth_info_file = AUTH_INFO_FILE
        self.browser_state_dir = BROWSER_STATE_DIR

    def is_authenticated(self) -> bool:
        """Check if valid authentication exists"""
        if not self.state_file.exists():
            return False
        age_days = (time.time() - self.state_file.stat().st_mtime) / 86400
        if age_days > 7:
            print(f"⚠️ Browser state is {age_days:.1f} days old, may need re-authentication")
        return True

    def get_auth_info(self) -> Dict[str, Any]:
        """Get authentication information"""
        info = {
            'authenticated': self.is_authenticated(),
            'state_file': str(self.state_file),
            'state_exists': self.state_file.exists()
        }
        if self.auth_info_file.exists():
            try:
                with open(self.auth_info_file, 'r') as f:
                    info.update(json.load(f))
            except Exception:
                pass
        if info['state_exists']:
            info['state_age_hours'] = (time.time() - self.state_file.stat().st_mtime) / 3600
        return info

    def setup_auth(self, headless: bool = False, timeout_minutes: int = 10) -> bool:
        """Perform interactive Binance authentication setup"""
        print("🔐 Starting Binance authentication setup...")
        print(f"  Timeout: {timeout_minutes} minutes")

        playwright = None
        context = None

        try:
            playwright = sync_playwright().start()
            context = BrowserFactory.launch_persistent_context(playwright, headless=headless)
            page = context.new_page()
            page.goto("https://www.binance.com/en/my/dashboard", wait_until="domcontentloaded")

            # Check if already authenticated
            try:
                page.wait_for_selector(BINANCE_AUTH_CHECK_SELECTOR, timeout=5000)
                print("  ✅ Already authenticated!")
                self._save_browser_state(context)
                return True
            except Exception:
                pass

            # Navigate to login
            page.goto(BINANCE_LOGIN_URL, wait_until="domcontentloaded")

            print("\n  ⏳ Please log in to your Binance account...")
            print(f"  ⏱️ Waiting up to {timeout_minutes} minutes for login...")

            try:
                timeout_ms = int(timeout_minutes * 60 * 1000)
                # Wait for redirect to dashboard or user icon
                page.wait_for_selector(BINANCE_AUTH_CHECK_SELECTOR, timeout=timeout_ms)
                print("  ✅ Login successful!")
                self._save_browser_state(context)
                self._save_auth_info()
                return True
            except Exception as e:
                print(f"  ❌ Authentication timeout: {e}")
                return False

        except Exception as e:
            print(f"  ❌ Error: {e}")
            return False
        finally:
            if context:
                try:
                    context.close()
                except Exception:
                    pass
            if playwright:
                try:
                    playwright.stop()
                except Exception:
                    pass

    def _save_browser_state(self, context: BrowserContext):
        """Save browser state to disk"""
        try:
            context.storage_state(path=str(self.state_file))
            print(f"  💾 Saved browser state")
        except Exception as e:
            print(f"  ❌ Failed to save browser state: {e}")
            raise

    def _save_auth_info(self):
        """Save authentication metadata"""
        try:
            info = {
                'authenticated_at': time.time(),
                'authenticated_at_iso': time.strftime('%Y-%m-%d %H:%M:%S'),
                'service': 'binance'
            }
            with open(self.auth_info_file, 'w') as f:
                json.dump(info, f, indent=2)
        except Exception:
            pass

    def clear_auth(self) -> bool:
        """Clear all authentication data"""
        print("🗑️ Clearing authentication data...")
        try:
            if self.state_file.exists():
                self.state_file.unlink()
                print("  ✅ Removed browser state")
            if self.auth_info_file.exists():
                self.auth_info_file.unlink()
                print("  ✅ Removed auth info")
            if self.browser_state_dir.exists():
                shutil.rmtree(self.browser_state_dir)
                self.browser_state_dir.mkdir(parents=True, exist_ok=True)
                print("  ✅ Cleared browser data")
            return True
        except Exception as e:
            print(f"  ❌ Error clearing auth: {e}")
            return False

    def re_auth(self, headless: bool = False, timeout_minutes: int = 10) -> bool:
        """Re-authenticate (clear + setup)"""
        self.clear_auth()
        return self.setup_auth(headless, timeout_minutes)

    def validate_auth(self) -> bool:
        """Validate that stored authentication works"""
        if not self.is_authenticated():
            return False

        print("🔍 Validating Binance authentication...")
        playwright = None
        context = None

        try:
            playwright = sync_playwright().start()
            context = BrowserFactory.launch_persistent_context(playwright, headless=True)
            page = context.new_page()
            page.goto("https://www.binance.com/en/my/dashboard", wait_until="domcontentloaded", timeout=30000)

            try:
                page.wait_for_selector(BINANCE_AUTH_CHECK_SELECTOR, timeout=10000)
                print("  ✅ Authentication is valid")
                return True
            except Exception:
                print("  ❌ Authentication is invalid (not logged in)")
                return False

        except Exception as e:
            print(f"  ❌ Validation failed: {e}")
            return False
        finally:
            if context:
                try:
                    context.close()
                except Exception:
                    pass
            if playwright:
                try:
                    playwright.stop()
                except Exception:
                    pass


def main():
    parser = argparse.ArgumentParser(description='Manage Binance authentication')
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    setup_parser = subparsers.add_parser('setup', help='Setup authentication')
    setup_parser.add_argument('--headless', action='store_true')
    setup_parser.add_argument('--timeout', type=float, default=10)

    subparsers.add_parser('status', help='Check authentication status')
    subparsers.add_parser('validate', help='Validate authentication')
    subparsers.add_parser('clear', help='Clear authentication')

    reauth_parser = subparsers.add_parser('reauth', help='Re-authenticate')
    reauth_parser.add_argument('--timeout', type=float, default=10)

    args = parser.parse_args()
    auth = AuthManager()

    if args.command == 'setup':
        if auth.setup_auth(headless=args.headless, timeout_minutes=args.timeout):
            print("\n✅ Binance authentication setup complete!")
        else:
            print("\n❌ Authentication setup failed")
            exit(1)
    elif args.command == 'status':
        info = auth.get_auth_info()
        print("\n🔐 Authentication Status:")
        print(f"  Authenticated: {'Yes' if info['authenticated'] else 'No'}")
        if info.get('state_age_hours'):
            print(f"  State age: {info['state_age_hours']:.1f} hours")
        if info.get('authenticated_at_iso'):
            print(f"  Last auth: {info['authenticated_at_iso']}")
    elif args.command == 'validate':
        if auth.validate_auth():
            print("Authentication is valid")
        else:
            print("Authentication is invalid. Run: auth_manager.py setup")
    elif args.command == 'clear':
        auth.clear_auth()
    elif args.command == 'reauth':
        if auth.re_auth(timeout_minutes=args.timeout):
            print("\n✅ Re-authentication complete!")
        else:
            print("\n❌ Re-authentication failed")
            exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
