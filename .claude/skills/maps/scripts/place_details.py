#!/usr/bin/env python3
"""Get detailed information about a place using Google Places API."""

import argparse
import json
import os
import urllib.request


def get_place_details(
    place_id: str,
    output_json: bool = False,
):
    """Get detailed information about a place.

    Args:
        place_id: Google Place ID
        output_json: Output as JSON
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        print("Error: GOOGLE_MAPS_API_KEY environment variable not set")
        return None

    # Build request URL for Places API (New)
    base_url = f"https://places.googleapis.com/v1/places/{place_id}"

    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "id,displayName,formattedAddress,rating,userRatingCount,websiteUri,nationalPhoneNumber,internationalPhoneNumber,regularOpeningHours,priceLevel,types,editorialSummary,reviews,photos,location,businessStatus,googleMapsUri"
    }

    req = urllib.request.Request(base_url, headers=headers)

    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"API Error: {e.code} - {error_body}")
        return None

    if output_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return data

    # Format output
    name = data.get("displayName", {}).get("text", "알 수 없음")
    address = data.get("formattedAddress", "주소 없음")
    rating = data.get("rating")
    review_count = data.get("userRatingCount", 0)
    phone = data.get("nationalPhoneNumber") or data.get("internationalPhoneNumber")
    website = data.get("websiteUri")
    maps_url = data.get("googleMapsUri")
    status = data.get("businessStatus", "")
    price_level = data.get("priceLevel")

    print(f"📍 {name}\n")
    print(f"주소: {address}")

    if rating:
        stars = "⭐" * int(rating)
        print(f"평점: {stars} {rating:.1f} ({review_count}개 리뷰)")

    if price_level:
        price_text = {
            "PRICE_LEVEL_FREE": "무료",
            "PRICE_LEVEL_INEXPENSIVE": "저렴 ($)",
            "PRICE_LEVEL_MODERATE": "보통 ($$)",
            "PRICE_LEVEL_EXPENSIVE": "비쌈 ($$$)",
            "PRICE_LEVEL_VERY_EXPENSIVE": "매우 비쌈 ($$$$)"
        }.get(price_level, price_level)
        print(f"가격대: {price_text}")

    if status and status != "OPERATIONAL":
        status_text = {
            "CLOSED_TEMPORARILY": "일시 휴업",
            "CLOSED_PERMANENTLY": "영업 종료"
        }.get(status, status)
        print(f"상태: ⚠️ {status_text}")

    if phone:
        print(f"전화: {phone}")

    if website:
        print(f"웹사이트: {website}")

    # Opening hours
    opening_hours = data.get("regularOpeningHours", {})
    weekday_text = opening_hours.get("weekdayDescriptions", [])
    if weekday_text:
        print(f"\n🕐 영업시간:")
        for day in weekday_text:
            print(f"   {day}")

    # Editorial summary
    summary = data.get("editorialSummary", {}).get("text")
    if summary:
        print(f"\n📝 설명:")
        print(f"   {summary}")

    # Location
    location = data.get("location", {})
    lat = location.get("latitude")
    lng = location.get("longitude")
    if lat and lng:
        print(f"\n좌표: {lat}, {lng}")

    if maps_url:
        print(f"\n🔗 Google Maps: {maps_url}")

    # Reviews (show top 2)
    reviews = data.get("reviews", [])
    if reviews:
        print(f"\n💬 최근 리뷰 ({len(reviews)}개 중 상위 2개):")
        for review in reviews[:2]:
            author = review.get("authorAttribution", {}).get("displayName", "익명")
            text = review.get("text", {}).get("text", "")
            review_rating = review.get("rating")
            publish_time = review.get("relativePublishTimeDescription", "")

            if text:
                text_short = text[:100] + "..." if len(text) > 100 else text
                rating_stars = "⭐" * int(review_rating) if review_rating else ""
                print(f"   • {author} {rating_stars} ({publish_time})")
                print(f"     \"{text_short}\"")

    print(f"\n📋 Place ID: {place_id}")

    return data


def main():
    parser = argparse.ArgumentParser(description="Get place details")
    parser.add_argument("place_id", help="Google Place ID")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    get_place_details(
        place_id=args.place_id,
        output_json=args.json,
    )


if __name__ == "__main__":
    main()
