#!/usr/bin/env python3
"""Delete a calendar event."""

import argparse
from typing import Optional

from calendar_auth import get_calendar_service


def delete_event(
    event_id: str,
    calendar_id: str = "primary",
    credentials_path: Optional[str] = None,
):
    """Delete a calendar event.

    Args:
        event_id: Event ID to delete
        calendar_id: Calendar ID (default: primary)
        credentials_path: Path to credentials.json
    """
    service = get_calendar_service(credentials_path)

    # Get event details first for confirmation
    event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
    summary = event.get("summary", "(제목 없음)")

    # Delete event
    service.events().delete(calendarId=calendar_id, eventId=event_id).execute()

    print(f"🗑️ 일정이 삭제되었습니다: {summary}")
    print(f"   Event ID: {event_id}")


def main():
    parser = argparse.ArgumentParser(description="Delete a calendar event")
    parser.add_argument("event_id", help="Event ID to delete")
    parser.add_argument("--calendar", default="primary", help="Calendar ID")
    parser.add_argument("--credentials", help="Path to credentials.json")
    args = parser.parse_args()

    delete_event(
        event_id=args.event_id,
        calendar_id=args.calendar,
        credentials_path=args.credentials,
    )


if __name__ == "__main__":
    main()
