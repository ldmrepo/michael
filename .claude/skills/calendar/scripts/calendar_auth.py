#!/usr/bin/env python3
"""Google Calendar API authentication utilities.

Shared authentication logic for all Calendar scripts.
"""

import os
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Default scopes for Calendar access
DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
]


def get_credentials_path(custom_path: Optional[str] = None) -> Path:
    """Get path to credentials.json file."""
    if custom_path:
        return Path(custom_path)

    # Check environment variable
    env_path = os.environ.get("CALENDAR_CREDENTIALS_PATH")
    if env_path:
        return Path(env_path)

    # Check skill root directory first
    skill_creds = Path(__file__).parent.parent / "credentials.json"
    if skill_creds.exists():
        return skill_creds

    # Fallback to Gmail integration credentials
    gmail_creds = Path(__file__).parent.parent.parent / "gmail-integration" / "credentials.json"
    if gmail_creds.exists():
        return gmail_creds

    return skill_creds


def get_token_path(credentials_path: Path) -> Path:
    """Get path to token.json file (in skill root directory)."""
    return Path(__file__).parent.parent / "token.json"


def authenticate(
    credentials_path: Optional[str] = None,
    scopes: Optional[list[str]] = None,
) -> Credentials:
    """Authenticate with Calendar API and return credentials.

    Args:
        credentials_path: Path to credentials.json file
        scopes: OAuth scopes to request (defaults to calendar full access)

    Returns:
        Authenticated credentials object
    """
    scopes = scopes or DEFAULT_SCOPES
    creds_path = get_credentials_path(credentials_path)
    token_path = get_token_path(creds_path)

    if not creds_path.exists():
        raise FileNotFoundError(
            f"Credentials file not found at {creds_path}\n"
            "Please download OAuth credentials from Google Cloud Console.\n"
            "Or create a symlink to Gmail credentials:\n"
            "  ln -s ../gmail-integration/credentials.json credentials.json"
        )

    creds = None

    # Load existing token if available
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)

    # Refresh or re-authenticate if needed
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired token...")
            creds.refresh(Request())
        else:
            print("Opening browser for authentication...")
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), scopes)
            creds = flow.run_local_server(port=0)

        # Save token for future use with restricted permissions
        with open(token_path, "w") as f:
            f.write(creds.to_json())
        os.chmod(token_path, 0o600)  # Restrict to owner-only access
        print(f"Token saved to {token_path}")

    return creds


def get_calendar_service(credentials_path: Optional[str] = None):
    """Get authenticated Calendar API service.

    Args:
        credentials_path: Path to credentials.json file

    Returns:
        Calendar API service object
    """
    creds = authenticate(credentials_path)
    return build("calendar", "v3", credentials=creds)


if __name__ == "__main__":
    # Test authentication
    import argparse

    parser = argparse.ArgumentParser(description="Test Calendar authentication")
    parser.add_argument("--credentials", help="Path to credentials.json")
    args = parser.parse_args()

    service = get_calendar_service(args.credentials)
    calendar = service.calendarList().get(calendarId="primary").execute()

    print(f"Authenticated! Primary calendar: {calendar.get('summary')}")
    print(f"Time zone: {calendar.get('timeZone')}")
