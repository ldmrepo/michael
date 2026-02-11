#!/usr/bin/env python3
"""Create a new calendar event."""

import argparse
from datetime import datetime
from typing import Optional

from calendar_auth import get_calendar_service


def create_event(
    title: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    date: Optional[str] = None,
    all_day: bool = False,
    location: Optional[str] = None,
    description: Optional[str] = None,
    attendees: Optional[str] = None,
    calendar_id: str = "primary",
    timezone: Optional[str] = None,
    credentials_path: Optional[str] = None,
):
    """Create a calendar event.

    Args:
        title: Event title
        start: Start datetime (YYYY-MM-DD HH:MM)
        end: End datetime (YYYY-MM-DD HH:MM)
        date: Date for all-day event (YYYY-MM-DD)
        all_day: Create all-day event
        location: Event location
        description: Event description
        attendees: Comma-separated email addresses
        calendar_id: Calendar ID (default: primary)
        timezone: Timezone (default: system timezone)
        credentials_path: Path to credentials.json
    """
    service = get_calendar_service(credentials_path)

    # Get calendar timezone if not specified
    if not timezone:
        calendar = service.calendarList().get(calendarId=calendar_id).execute()
        timezone = calendar.get("timeZone", "Asia/Seoul")

    # Build event body
    event = {
        "summary": title,
    }

    if all_day or date:
        # All-day event
        event_date = date or (start.split()[0] if start else datetime.now().strftime("%Y-%m-%d"))
        event["start"] = {"date": event_date}
        event["end"] = {"date": event_date}
    else:
        # Timed event
        if not start:
            raise ValueError("Start time is required for non-all-day events")

        # Parse start time
        start_dt = datetime.strptime(start, "%Y-%m-%d %H:%M")
        event["start"] = {
            "dateTime": start_dt.isoformat(),
            "timeZone": timezone,
        }

        # Parse end time (default: 1 hour after start)
        if end:
            end_dt = datetime.strptime(end, "%Y-%m-%d %H:%M")
        else:
            from datetime import timedelta
            end_dt = start_dt + timedelta(hours=1)

        event["end"] = {
            "dateTime": end_dt.isoformat(),
            "timeZone": timezone,
        }

    # Optional fields
    if location:
        event["location"] = location

    if description:
        event["description"] = description

    if attendees:
        event["attendees"] = [
            {"email": email.strip()} for email in attendees.split(",")
        ]

    # Create event
    created_event = service.events().insert(calendarId=calendar_id, body=event).execute()

    # Output result
    print("✅ 일정이 생성되었습니다!\n")
    print(f"📅 {created_event.get('summary')}")

    start_info = created_event["start"]
    if "dateTime" in start_info:
        start_dt = datetime.fromisoformat(start_info["dateTime"].replace("Z", "+00:00"))
        end_info = created_event["end"]
        end_dt = datetime.fromisoformat(end_info["dateTime"].replace("Z", "+00:00"))
        print(f"📆 {start_dt.strftime('%Y년 %m월 %d일 %H:%M')}-{end_dt.strftime('%H:%M')}")
    else:
        print(f"📆 {start_info['date']} (종일)")

    if location:
        print(f"📍 {location}")

    if attendees:
        attendee_list = created_event.get("attendees", [])
        print(f"👥 {len(attendee_list)}명 초대됨")

    print(f"\n🔗 {created_event.get('htmlLink')}")

    return created_event


def main():
    parser = argparse.ArgumentParser(description="Create a calendar event")
    parser.add_argument("--title", required=True, help="Event title")
    parser.add_argument("--start", help="Start datetime (YYYY-MM-DD HH:MM)")
    parser.add_argument("--end", help="End datetime (YYYY-MM-DD HH:MM)")
    parser.add_argument("--date", help="Date for all-day event (YYYY-MM-DD)")
    parser.add_argument("--all-day", action="store_true", help="Create all-day event")
    parser.add_argument("--location", help="Event location")
    parser.add_argument("--description", help="Event description")
    parser.add_argument("--attendees", help="Comma-separated email addresses")
    parser.add_argument("--calendar", default="primary", help="Calendar ID")
    parser.add_argument("--timezone", help="Timezone")
    parser.add_argument("--credentials", help="Path to credentials.json")
    args = parser.parse_args()

    create_event(
        title=args.title,
        start=args.start,
        end=args.end,
        date=args.date,
        all_day=args.all_day,
        location=args.location,
        description=args.description,
        attendees=args.attendees,
        calendar_id=args.calendar,
        timezone=args.timezone,
        credentials_path=args.credentials,
    )


if __name__ == "__main__":
    main()
