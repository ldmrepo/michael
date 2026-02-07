#!/usr/bin/env python3
"""Get directions between two locations using Google Directions API."""

import argparse
import json
import os
import urllib.request
import urllib.parse


def get_directions(
    origin: str,
    destination: str,
    mode: str = "driving",
    departure_time: str = None,
    avoid: str = None,
    output_json: bool = False,
):
    """Get directions between two locations.

    Args:
        origin: Starting point (address or lat,lng)
        destination: Ending point (address or lat,lng)
        mode: Travel mode (driving, walking, bicycling, transit)
        departure_time: Departure time (now or timestamp)
        avoid: Features to avoid (tolls, highways, ferries)
        output_json: Output as JSON
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        print("Error: GOOGLE_MAPS_API_KEY environment variable not set")
        return None

    # Build request URL
    base_url = "https://maps.googleapis.com/maps/api/directions/json"

    params = {
        "origin": origin,
        "destination": destination,
        "mode": mode,
        "key": api_key,
        "language": "ko",
        "units": "metric"
    }

    if departure_time:
        params["departure_time"] = departure_time

    if avoid:
        params["avoid"] = avoid

    url = f"{base_url}?{urllib.parse.urlencode(params)}"

    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"API Error: {e.code}")
        return None

    if data.get("status") != "OK":
        error_msg = data.get("error_message", data.get("status"))
        print(f"Error: {error_msg}")
        return None

    if output_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return data

    routes = data.get("routes", [])
    if not routes:
        print("경로를 찾을 수 없습니다.")
        return None

    route = routes[0]
    legs = route.get("legs", [])

    if not legs:
        return None

    leg = legs[0]

    mode_emoji = {
        "driving": "🚗",
        "walking": "🚶",
        "bicycling": "🚴",
        "transit": "🚇"
    }.get(mode, "📍")

    print(f"{mode_emoji} 길찾기 결과\n")
    print(f"출발: {leg.get('start_address')}")
    print(f"도착: {leg.get('end_address')}")
    print()

    distance = leg.get("distance", {}).get("text", "알 수 없음")
    duration = leg.get("duration", {}).get("text", "알 수 없음")

    print(f"📏 총 거리: {distance}")
    print(f"⏱️ 예상 시간: {duration}")

    # Traffic info for driving
    if mode == "driving" and "duration_in_traffic" in leg:
        traffic_duration = leg["duration_in_traffic"].get("text")
        print(f"🚦 교통 고려: {traffic_duration}")

    print()

    # Show step-by-step directions
    steps = leg.get("steps", [])
    print(f"📋 경로 안내 ({len(steps)}단계):\n")

    for i, step in enumerate(steps, 1):
        instruction = step.get("html_instructions", "")
        # Remove HTML tags
        import re
        instruction = re.sub(r"<[^>]+>", " ", instruction)
        instruction = re.sub(r"\s+", " ", instruction).strip()

        step_distance = step.get("distance", {}).get("text", "")
        step_duration = step.get("duration", {}).get("text", "")

        # Transit specific info
        transit_details = step.get("transit_details")
        if transit_details:
            line = transit_details.get("line", {})
            line_name = line.get("short_name") or line.get("name", "")
            vehicle = line.get("vehicle", {}).get("name", "")
            departure_stop = transit_details.get("departure_stop", {}).get("name", "")
            arrival_stop = transit_details.get("arrival_stop", {}).get("name", "")
            num_stops = transit_details.get("num_stops", 0)

            print(f"{i}. {vehicle} {line_name}")
            print(f"   {departure_stop} → {arrival_stop} ({num_stops}정거장)")
        else:
            print(f"{i}. {instruction}")

        if step_distance and step_duration:
            print(f"   ({step_distance}, {step_duration})")
        print()

    return data


def main():
    parser = argparse.ArgumentParser(description="Get directions between two locations")
    parser.add_argument("origin", help="Starting point")
    parser.add_argument("destination", help="Ending point")
    parser.add_argument("--mode", default="driving",
                        choices=["driving", "walking", "bicycling", "transit"],
                        help="Travel mode")
    parser.add_argument("--departure-time", help="Departure time (now or timestamp)")
    parser.add_argument("--avoid", help="Features to avoid (tolls, highways, ferries)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    get_directions(
        origin=args.origin,
        destination=args.destination,
        mode=args.mode,
        departure_time=args.departure_time,
        avoid=args.avoid,
        output_json=args.json,
    )


if __name__ == "__main__":
    main()
