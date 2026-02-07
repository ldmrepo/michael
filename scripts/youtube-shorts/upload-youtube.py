#!/usr/bin/env python3
"""Upload video to YouTube using YouTube Data API v3."""

import argparse
import json
import os
import sys
import http.client
import urllib.parse
import urllib.request
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading


# OAuth 2.0 settings
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
REDIRECT_URI = "http://localhost:8085"
TOKEN_FILE = os.path.expanduser("~/.config/michael/youtube_token.json")


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback."""

    auth_code = None

    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)

        if "code" in params:
            OAuthCallbackHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Authorization successful!</h1><p>You can close this window.</p></body></html>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Authorization failed")

    def log_message(self, format, *args):
        pass  # Suppress logging


def load_credentials():
    """Load saved OAuth credentials."""
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    return None


def save_credentials(credentials):
    """Save OAuth credentials."""
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        json.dump(credentials, f)


def get_client_config():
    """Get OAuth client configuration."""
    client_id = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("Error: YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET must be set")
        print("Create OAuth credentials at: https://console.cloud.google.com/apis/credentials")
        sys.exit(1)

    return client_id, client_secret


def refresh_access_token(credentials):
    """Refresh the access token using refresh token."""
    client_id, client_secret = get_client_config()

    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": credentials["refresh_token"],
        "grant_type": "refresh_token",
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    try:
        with urllib.request.urlopen(req) as response:
            token_data = json.loads(response.read().decode("utf-8"))
            credentials["access_token"] = token_data["access_token"]
            if "refresh_token" in token_data:
                credentials["refresh_token"] = token_data["refresh_token"]
            save_credentials(credentials)
            return credentials
    except urllib.error.HTTPError as e:
        print(f"Token refresh failed: {e.code}")
        return None


def authenticate():
    """Authenticate with YouTube API using OAuth 2.0."""
    credentials = load_credentials()

    if credentials:
        # Try to refresh existing token
        refreshed = refresh_access_token(credentials)
        if refreshed:
            return refreshed

    # Need new authentication
    client_id, client_secret = get_client_config()

    # Build authorization URL
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    })

    print("🔐 Opening browser for YouTube authorization...")
    print(f"   If browser doesn't open, visit: {auth_url}")

    # Start local server for callback
    server = HTTPServer(("localhost", 8085), OAuthCallbackHandler)
    server_thread = threading.Thread(target=server.handle_request)
    server_thread.start()

    # Open browser
    webbrowser.open(auth_url)

    # Wait for callback
    server_thread.join(timeout=120)
    server.server_close()

    if not OAuthCallbackHandler.auth_code:
        print("❌ Authorization failed or timed out")
        sys.exit(1)

    # Exchange code for tokens
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "code": OAuthCallbackHandler.auth_code,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    try:
        with urllib.request.urlopen(req) as response:
            credentials = json.loads(response.read().decode("utf-8"))
            save_credentials(credentials)
            print("✅ Authorization successful!")
            return credentials
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"❌ Token exchange failed: {e.code}")
        print(f"   Details: {error_body}")
        sys.exit(1)


def upload_video(
    video_path: str,
    title: str,
    description: str = "",
    tags: list = None,
    category: str = "22",  # People & Blogs
    privacy: str = "public",
    is_short: bool = True,
):
    """Upload video to YouTube.

    Args:
        video_path: Path to the video file
        title: Video title
        description: Video description
        tags: List of tags
        category: YouTube category ID
        privacy: Privacy status (public, private, unlisted)
        is_short: Whether this is a YouTube Short

    Returns:
        Video ID if successful, None otherwise
    """
    if not os.path.exists(video_path):
        print(f"❌ Video file not found: {video_path}")
        return None

    credentials = authenticate()
    access_token = credentials["access_token"]

    # Prepare metadata
    if is_short and "#Shorts" not in title:
        title = f"{title} #Shorts"

    if tags is None:
        tags = []
    if is_short and "Shorts" not in tags:
        tags.append("Shorts")

    video_metadata = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        }
    }

    print(f"📤 Uploading to YouTube...")
    print(f"   Title: {title}")
    print(f"   Privacy: {privacy}")

    # Upload using resumable upload
    file_size = os.path.getsize(video_path)
    print(f"   File size: {file_size / (1024*1024):.2f} MB")

    # Step 1: Initialize upload
    init_url = "https://www.googleapis.com/upload/youtube/v3/videos?" + urllib.parse.urlencode({
        "uploadType": "resumable",
        "part": "snippet,status"
    })

    init_headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Upload-Content-Type": "video/*",
        "X-Upload-Content-Length": str(file_size),
    }

    req = urllib.request.Request(
        init_url,
        data=json.dumps(video_metadata).encode("utf-8"),
        headers=init_headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as response:
            upload_url = response.headers.get("Location")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"❌ Upload initialization failed: {e.code}")
        print(f"   Details: {error_body}")
        return None

    # Step 2: Upload video data
    print("   Uploading video data...")

    with open(video_path, "rb") as video_file:
        video_data = video_file.read()

    upload_headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "video/*",
        "Content-Length": str(file_size),
    }

    req = urllib.request.Request(
        upload_url,
        data=video_data,
        headers=upload_headers,
        method="PUT"
    )

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            video_id = result.get("id")

            if video_id:
                video_url = f"https://youtube.com/shorts/{video_id}" if is_short else f"https://youtube.com/watch?v={video_id}"
                print(f"✅ Upload successful!")
                print(f"   Video ID: {video_id}")
                print(f"   URL: {video_url}")
                return video_id
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"❌ Upload failed: {e.code}")
        print(f"   Details: {error_body}")
        return None

    return None


def main():
    parser = argparse.ArgumentParser(description="Upload video to YouTube")
    parser.add_argument("--video", "-v", required=True, help="Path to video file")
    parser.add_argument("--title", "-t", required=True, help="Video title")
    parser.add_argument("--description", "-d", default="", help="Video description")
    parser.add_argument("--tags", default="", help="Comma-separated tags")
    parser.add_argument("--category", default="22", help="YouTube category ID")
    parser.add_argument("--privacy", default="public", choices=["public", "private", "unlisted"])
    parser.add_argument("--no-short", action="store_true", help="Don't mark as Short")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []

    video_id = upload_video(
        video_path=args.video,
        title=args.title,
        description=args.description,
        tags=tags,
        category=args.category,
        privacy=args.privacy,
        is_short=not args.no_short,
    )

    if args.json:
        output = {
            "success": video_id is not None,
            "video_id": video_id,
            "url": f"https://youtube.com/shorts/{video_id}" if video_id else None,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
