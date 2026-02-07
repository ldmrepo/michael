#!/usr/bin/env python3
"""Search for places using Google Places API."""

import argparse
import json
import os
import urllib.request
import urllib.parse


def search_places(
    query: str,
    location: str = None,
    radius: int = 5000,
    place_type: str = None,
    max_results: int = 10,
    output_json: bool = False,
):
    """Search for places.

    Args:
        query: Search query (e.g., "카페", "맛집")
        location: Center point for search (lat,lng or address)
        radius: Search radius in meters (default: 5000)
        place_type: Filter by place type (restaurant, cafe, etc.)
        max_results: Maximum number of results
        output_json: Output as JSON
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        print("Error: GOOGLE_MAPS_API_KEY environment variable not set")
        return []

    # Build request URL for Places API (New) Text Search
    base_url = "https://places.googleapis.com/v1/places:searchText"

    # Build request body
    request_body = {
        "textQuery": query,
        "maxResultCount": min(max_results, 20),
        "languageCode": "ko"
    }

    if location:
        # If location is provided, add location bias
        if "," in location:
            lat, lng = location.split(",")
            request_body["locationBias"] = {
                "circle": {
                    "center": {"latitude": float(lat), "longitude": float(lng)},
                    "radius": float(radius)
                }
            }

    if place_type:
        request_body["includedType"] = place_type

    # Make request
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.id,places.location,places.types,places.businessStatus"
    }

    req = urllib.request.Request(
        base_url,
        data=json.dumps(request_body).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"API Error: {e.code} - {error_body}")
        return []

    places = data.get("places", [])

    if output_json:
        print(json.dumps(places, ensure_ascii=False, indent=2))
        return places

    if not places:
        print(f"'{query}' 검색 결과가 없습니다.")
        return []

    print(f"'{query}' 검색 결과 ({len(places)}개)\n")

    for i, place in enumerate(places, 1):
        name = place.get("displayName", {}).get("text", "알 수 없음")
        address = place.get("formattedAddress", "주소 없음")
        rating = place.get("rating")
        review_count = place.get("userRatingCount", 0)
        place_id = place.get("id", "")
        status = place.get("businessStatus", "")

        print(f"{i}. {name}")
        print(f"   📍 {address}")

        if rating:
            stars = "⭐" * int(rating)
            print(f"   {stars} {rating:.1f} ({review_count}개 리뷰)")

        if status and status != "OPERATIONAL":
            status_text = {
                "CLOSED_TEMPORARILY": "일시 휴업",
                "CLOSED_PERMANENTLY": "영업 종료"
            }.get(status, status)
            print(f"   ⚠️ {status_text}")

        print(f"   🔗 Place ID: {place_id}")
        print()

    return places


def main():
    parser = argparse.ArgumentParser(description="Search for places")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--location", help="Center location (lat,lng or address)")
    parser.add_argument("--radius", type=int, default=5000, help="Search radius in meters")
    parser.add_argument("--type", dest="place_type", help="Place type filter")
    parser.add_argument("--max-results", type=int, default=10, help="Maximum results")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    search_places(
        query=args.query,
        location=args.location,
        radius=args.radius,
        place_type=args.place_type,
        max_results=args.max_results,
        output_json=args.json,
    )


if __name__ == "__main__":
    main()
