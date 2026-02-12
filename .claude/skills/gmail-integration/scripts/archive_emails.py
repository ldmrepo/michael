#!/usr/bin/env python3
"""Archive (remove INBOX label) emails matching specific senders/subjects.

Searches for emails matching predefined patterns and archives them in batch.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from gmail_auth import get_gmail_service


# Define search queries - each will be combined with "in:inbox"
ARCHIVE_QUERIES = [
    # Inflearn
    '(from:인프런 OR from:inflearn) 설 연휴',
    # LG CNS / D-Talks
    '(from:lgcns OR subject:D-Talks)',
    # Seeking Alpha (multiple)
    'from:seekingalpha.com',
    # Stocktwits
    'from:stocktwits.com',
    # Docker
    'from:docker.com',
    # Notion
    'from:notion.so',
    # Mobbin
    'from:mobbin.com',
    # Unstract
    'from:unstract',
    # CoinGecko
    'from:coingecko.com',
    # Google Maps Platform
    'from:google.com subject:"Maps Platform"',
    # LinkedIn
    'from:linkedin.com',
    # Google Security alerts
    'from:google.com (subject:보안 OR subject:Security)',
    # Polymarket
    'from:polymarket.com',
]


def collect_message_ids(service, queries: list[str]) -> dict[str, list[dict]]:
    """Search for messages matching each query and collect unique IDs.

    Returns:
        Dict mapping query to list of {id, subject, from} for reporting.
    """
    results = {}
    seen_ids = set()

    for query in queries:
        full_query = f"in:inbox {query}"
        print(f"Searching: {full_query}")

        try:
            response = service.users().messages().list(
                userId="me",
                q=full_query,
                maxResults=50,
            ).execute()
        except Exception as e:
            print(f"  ERROR searching: {e}")
            continue

        messages = response.get("messages", [])
        if not messages:
            print(f"  No messages found.")
            continue

        query_results = []
        for msg in messages:
            msg_id = msg["id"]
            if msg_id in seen_ids:
                continue
            seen_ids.add(msg_id)

            # Fetch minimal metadata for reporting
            try:
                msg_data = service.users().messages().get(
                    userId="me",
                    id=msg_id,
                    format="metadata",
                    metadataHeaders=["From", "Subject", "Date"],
                ).execute()
                headers = {h["name"]: h["value"] for h in msg_data["payload"]["headers"]}
                query_results.append({
                    "id": msg_id,
                    "from": headers.get("From", "?"),
                    "subject": headers.get("Subject", "(no subject)"),
                    "date": headers.get("Date", "?"),
                })
            except Exception as e:
                # Still archive even if metadata fetch fails
                query_results.append({
                    "id": msg_id,
                    "from": "?",
                    "subject": f"(metadata error: {e})",
                    "date": "?",
                })

        results[query] = query_results
        print(f"  Found {len(query_results)} message(s).")

    return results


def archive_messages(service, message_ids: list[str]) -> int:
    """Archive messages by removing INBOX label using batch modify.

    Returns:
        Number of messages archived.
    """
    if not message_ids:
        return 0

    # Gmail batch modify supports up to 1000 IDs at once
    batch_size = 1000
    archived = 0

    for i in range(0, len(message_ids), batch_size):
        batch = message_ids[i:i + batch_size]
        try:
            service.users().messages().batchModify(
                userId="me",
                body={
                    "ids": batch,
                    "removeLabelIds": ["INBOX"],
                },
            ).execute()
            archived += len(batch)
            print(f"  Archived batch: {len(batch)} messages")
        except Exception as e:
            print(f"  ERROR archiving batch: {e}")

    return archived


def main():
    print("=" * 60)
    print("Gmail Inbox Archiver")
    print("=" * 60)
    print()

    # Authenticate
    creds_path = str(Path(__file__).parent.parent / "credentials.json")
    service = get_gmail_service(creds_path)
    print("Authenticated successfully.\n")

    # Collect messages
    print("--- Searching for messages to archive ---\n")
    results = collect_message_ids(service, ARCHIVE_QUERIES)

    # Summarize findings
    all_ids = []
    print("\n" + "=" * 60)
    print("SUMMARY OF FOUND EMAILS")
    print("=" * 60)

    total_found = 0
    for query, messages in results.items():
        if messages:
            print(f"\n[{query}] - {len(messages)} email(s):")
            for m in messages:
                print(f"  - {m['from'][:50]}")
                print(f"    Subject: {m['subject'][:70]}")
                print(f"    Date: {m['date']}")
            all_ids.extend(m["id"] for m in messages)
            total_found += len(messages)

    print(f"\nTotal unique emails to archive: {total_found}")

    if not all_ids:
        print("Nothing to archive. Done.")
        return

    # Archive
    print("\n--- Archiving ---\n")
    archived = archive_messages(service, all_ids)

    print(f"\nDone! Archived {archived} email(s) from inbox.")


if __name__ == "__main__":
    main()
