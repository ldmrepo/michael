#!/usr/bin/env python3
"""List upcoming calendar events."""

import argparse
import json
from datetime import datetime, timedelta
from typing import Optional

from calendar_auth import get_calendar_service


def list_events(
    days: int = 1,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_results: int = 50,
    calendar_id: str = "primary",
    output_json: bool = False,
    credentials_path: Optional[str] = None,
):
    """List calendar events.

    Args:
        days: Number of days to look ahead (ignored if start_date/end_date provided)
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        max_results: Maximum number of events to return
        calendar_id: Calendar ID (default: primary)
        output_json: Output as JSON
        credentials_path: Path to credentials.json
    """
    service = get_calendar_service(credentials_path)

    # Determine time range
    if start_date:
        time_min = datetime.fromisoformat(start_date).replace(hour=0, minute=0, second=0)
    else:
        time_min = datetime.now().replace(hour=0, minute=0, second=0)

    if end_date:
        time_max = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59)
    else:
        time_max = time_min + timedelta(days=days)

    # Convert to RFC3339 format
    time_min_str = time_min.isoformat() + "Z"
    time_max_str = time_max.isoformat() + "Z"

    # Fetch events
    events_result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=time_min_str,
            timeMax=time_max_str,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = events_result.get("items", [])

    if output_json:
        print(json.dumps(events, ensure_ascii=False, indent=2))
        return events

    # Format output
    if not events:
        print("📅 일정이 없습니다.")
        return []

    date_str = time_min.strftime("%Y년 %m월 %d일")
    if days > 1 or end_date:
        end_str = time_max.strftime("%Y년 %m월 %d일")
        print(f"📅 일정 ({date_str} ~ {end_str})\n")
    else:
        print(f"📅 오늘의 일정 ({date_str})\n")

    for i, event in enumerate(events, 1):
        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))
        summary = event.get("summary", "(제목 없음)")

        # Parse time
        if "T" in start:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
            time_str = f"{start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')}"
        else:
            time_str = "종일"

        print(f"{i}. {time_str} | {summary}")

        # Location
        location = event.get("location")
        if location:
            print(f"   📍 {location}")

        # Attendees
        attendees = event.get("attendees", [])
        if attendees:
            print(f"   👥 {len(attendees)}명 참석")

        # Description (truncated)
        description = event.get("description", "")
        if description:
            desc_short = description[:50] + "..." if len(description) > 50 else description
            print(f"   📝 {desc_short}")

        print()

    print(f"총 {len(events)}개의 일정이 있습니다.")
    return events


def main():
    parser = argparse.ArgumentParser(description="List calendar events")
    parser.add_argument("--days", type=int, default=1, help="Number of days to look ahead")
    parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    parser.add_argument("--max-results", type=int, default=50, help="Maximum results")
    parser.add_argument("--calendar", default="primary", help="Calendar ID")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--credentials", help="Path to credentials.json")
    args = parser.parse_args()

    list_events(
        days=args.days,
        start_date=args.start,
        end_date=args.end,
        max_results=args.max_results,
        calendar_id=args.calendar,
        output_json=args.json,
        credentials_path=args.credentials,
    )


if __name__ == "__main__":
    main()
