#!/usr/bin/env python3
"""Get details of a specific calendar event."""

import argparse
import json
from datetime import datetime
from typing import Optional

from calendar_auth import get_calendar_service


def get_event(
    event_id: str,
    calendar_id: str = "primary",
    output_json: bool = False,
    credentials_path: Optional[str] = None,
):
    """Get event details.

    Args:
        event_id: Event ID
        calendar_id: Calendar ID (default: primary)
        output_json: Output as JSON
        credentials_path: Path to credentials.json
    """
    service = get_calendar_service(credentials_path)

    event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()

    if output_json:
        print(json.dumps(event, ensure_ascii=False, indent=2))
        return event

    # Format output
    print(f"📅 {event.get('summary', '(제목 없음)')}\n")

    # Time
    start_info = event["start"]
    end_info = event["end"]
    if "dateTime" in start_info:
        start_dt = datetime.fromisoformat(start_info["dateTime"].replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_info["dateTime"].replace("Z", "+00:00"))
        print(f"📆 {start_dt.strftime('%Y년 %m월 %d일 %H:%M')} - {end_dt.strftime('%H:%M')}")
    else:
        print(f"📆 {start_info['date']} (종일)")

    # Location
    location = event.get("location")
    if location:
        print(f"📍 {location}")

    # Description
    description = event.get("description")
    if description:
        print(f"\n📝 설명:\n{description}")

    # Attendees
    attendees = event.get("attendees", [])
    if attendees:
        print(f"\n👥 참석자 ({len(attendees)}명):")
        for attendee in attendees:
            email = attendee.get("email")
            status = attendee.get("responseStatus", "needsAction")
            status_emoji = {
                "accepted": "✅",
                "declined": "❌",
                "tentative": "❓",
                "needsAction": "⏳",
            }.get(status, "")
            organizer = " (주최자)" if attendee.get("organizer") else ""
            print(f"  {status_emoji} {email}{organizer}")

    # Link
    print(f"\n🔗 {event.get('htmlLink')}")

    # Metadata
    print(f"\n📋 Event ID: {event.get('id')}")
    print(f"📋 Status: {event.get('status')}")

    return event


def main():
    parser = argparse.ArgumentParser(description="Get calendar event details")
    parser.add_argument("event_id", help="Event ID")
    parser.add_argument("--calendar", default="primary", help="Calendar ID")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--credentials", help="Path to credentials.json")
    args = parser.parse_args()

    get_event(
        event_id=args.event_id,
        calendar_id=args.calendar,
        output_json=args.json,
        credentials_path=args.credentials,
    )


if __name__ == "__main__":
    main()
