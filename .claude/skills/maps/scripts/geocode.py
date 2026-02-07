#!/usr/bin/env python3
"""Convert between addresses and coordinates using Google Geocoding API."""

import argparse
import json
import os
import urllib.request
import urllib.parse


def geocode(
    address: str = None,
    reverse: str = None,
    output_json: bool = False,
):
    """Convert between addresses and coordinates.

    Args:
        address: Address to geocode
        reverse: Coordinates to reverse geocode (lat,lng)
        output_json: Output as JSON
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        print("Error: GOOGLE_MAPS_API_KEY environment variable not set")
        return None

    if not address and not reverse:
        print("Error: Provide either an address or coordinates")
        return None

    # Build request URL
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"

    params = {
        "key": api_key,
        "language": "ko"
    }

    if reverse:
        params["latlng"] = reverse
    else:
        params["address"] = address

    url = f"{base_url}?{urllib.parse.urlencode(params)}"

    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"API Error: {e.code}")
        return None

    if data.get("status") != "OK":
        status = data.get("status")
        if status == "ZERO_RESULTS":
            print("검색 결과가 없습니다.")
        else:
            error_msg = data.get("error_message", status)
            print(f"Error: {error_msg}")
        return None

    if output_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return data

    results = data.get("results", [])
    if not results:
        print("결과가 없습니다.")
        return None

    if reverse:
        print(f"📍 좌표 → 주소 변환\n")
        print(f"입력: {reverse}\n")
    else:
        print(f"📍 주소 → 좌표 변환\n")
        print(f"입력: {address}\n")

    for i, result in enumerate(results[:3], 1):  # Show top 3 results
        formatted_address = result.get("formatted_address", "알 수 없음")
        location = result.get("geometry", {}).get("location", {})
        lat = location.get("lat")
        lng = location.get("lng")
        place_id = result.get("place_id", "")

        # Get address components
        components = result.get("address_components", [])
        component_types = {}
        for comp in components:
            for t in comp.get("types", []):
                component_types[t] = comp.get("long_name")

        print(f"{i}. {formatted_address}")

        if lat and lng:
            print(f"   좌표: {lat}, {lng}")

        # Show detailed location info
        country = component_types.get("country")
        admin1 = component_types.get("administrative_area_level_1")
        locality = component_types.get("locality") or component_types.get("sublocality_level_1")

        if country or admin1 or locality:
            parts = [p for p in [country, admin1, locality] if p]
            print(f"   지역: {' > '.join(parts)}")

        print(f"   Place ID: {place_id}")
        print()

    return data


def main():
    parser = argparse.ArgumentParser(description="Convert between addresses and coordinates")
    parser.add_argument("address", nargs="?", help="Address to geocode")
    parser.add_argument("--reverse", "-r", help="Coordinates to reverse geocode (lat,lng)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    geocode(
        address=args.address,
        reverse=args.reverse,
        output_json=args.json,
    )


if __name__ == "__main__":
    main()
