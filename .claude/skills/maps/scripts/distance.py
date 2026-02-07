#!/usr/bin/env python3
"""Calculate distance and time between locations using Google Distance Matrix API."""

import argparse
import json
import os
import urllib.request
import urllib.parse


def get_distance(
    origin: str,
    destinations: str,
    mode: str = "driving",
    departure_time: str = None,
    output_json: bool = False,
):
    """Get distance and travel time between locations.

    Args:
        origin: Starting point (address or lat,lng)
        destinations: Comma-separated destination points
        mode: Travel mode (driving, walking, bicycling, transit)
        departure_time: Departure time (now or timestamp)
        output_json: Output as JSON
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        print("Error: GOOGLE_MAPS_API_KEY environment variable not set")
        return None

    # Build request URL
    base_url = "https://maps.googleapis.com/maps/api/distancematrix/json"

    params = {
        "origins": origin,
        "destinations": destinations,
        "mode": mode,
        "key": api_key,
        "language": "ko",
        "units": "metric"
    }

    if departure_time:
        params["departure_time"] = departure_time

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

    mode_emoji = {
        "driving": "🚗",
        "walking": "🚶",
        "bicycling": "🚴",
        "transit": "🚇"
    }.get(mode, "📍")

    origin_addresses = data.get("origin_addresses", [])
    destination_addresses = data.get("destination_addresses", [])
    rows = data.get("rows", [])

    if not rows or not rows[0].get("elements"):
        print("거리 정보를 찾을 수 없습니다.")
        return None

    origin_addr = origin_addresses[0] if origin_addresses else origin

    print(f"{mode_emoji} 거리/시간 계산 결과\n")
    print(f"출발: {origin_addr}\n")

    elements = rows[0].get("elements", [])

    for i, element in enumerate(elements):
        dest_addr = destination_addresses[i] if i < len(destination_addresses) else f"목적지 {i+1}"
        status = element.get("status")

        print(f"━━━ 목적지 {i+1}: {dest_addr}")

        if status != "OK":
            status_text = {
                "NOT_FOUND": "위치를 찾을 수 없음",
                "ZERO_RESULTS": "경로 없음",
                "MAX_ROUTE_LENGTH_EXCEEDED": "경로가 너무 김"
            }.get(status, status)
            print(f"   ⚠️ {status_text}")
        else:
            distance = element.get("distance", {}).get("text", "알 수 없음")
            duration = element.get("duration", {}).get("text", "알 수 없음")

            print(f"   📏 거리: {distance}")
            print(f"   ⏱️ 시간: {duration}")

            # Traffic info for driving
            if mode == "driving" and "duration_in_traffic" in element:
                traffic_duration = element["duration_in_traffic"].get("text")
                print(f"   🚦 교통 고려: {traffic_duration}")

        print()

    return data


def main():
    parser = argparse.ArgumentParser(description="Calculate distance between locations")
    parser.add_argument("origin", help="Starting point")
    parser.add_argument("destinations", help="Comma-separated destination points")
    parser.add_argument("--mode", default="driving",
                        choices=["driving", "walking", "bicycling", "transit"],
                        help="Travel mode")
    parser.add_argument("--departure-time", help="Departure time (now or timestamp)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    get_distance(
        origin=args.origin,
        destinations=args.destinations,
        mode=args.mode,
        departure_time=args.departure_time,
        output_json=args.json,
    )


if __name__ == "__main__":
    main()
