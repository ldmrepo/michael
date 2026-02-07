---
name: maps
description: |
  Google Maps 연동 스킬. 장소 검색, 길찾기, 거리/시간 계산, 주소 변환.
  다음 키워드에 사용: "지도", "maps", "장소", "길찾기", "directions", "거리", "distance", "위치", "location", "주소", "address", "근처", "nearby"
allowed-tools: Bash(python3:*), Read, Write
---

# Google Maps 스킬

Google Maps Platform API를 사용한 위치 기반 서비스.

## 사용 가능한 기능

### 1. 장소 검색 (Places Search)
```bash
python3 scripts/search_places.py "강남역 맛집" --type restaurant --radius 1000
python3 scripts/search_places.py "서울 카페" --max-results 5
```

### 2. 장소 상세 정보 (Place Details)
```bash
python3 scripts/place_details.py "ChIJN1t_tDeuEmsRUsoyG83frY4"  # place_id로 조회
```

### 3. 길찾기 (Directions)
```bash
python3 scripts/directions.py "강남역" "홍대입구역"
python3 scripts/directions.py "서울역" "부산역" --mode transit
python3 scripts/directions.py "37.5665,126.9780" "37.5512,126.9882"  # 좌표로도 가능
```

### 4. 거리/시간 계산 (Distance Matrix)
```bash
python3 scripts/distance.py "강남역" "홍대입구역,신촌역,이태원역"
python3 scripts/distance.py "서울" "대전,대구,부산" --mode driving
```

### 5. 주소 ↔ 좌표 변환 (Geocoding)
```bash
# 주소 → 좌표
python3 scripts/geocode.py "서울특별시 강남구 역삼동"

# 좌표 → 주소
python3 scripts/geocode.py --reverse "37.5665,126.9780"
```

## 이동 수단 옵션 (--mode)
- `driving`: 자동차 (기본값)
- `walking`: 도보
- `bicycling`: 자전거
- `transit`: 대중교통

## 장소 유형 (--type)
- `restaurant`: 음식점
- `cafe`: 카페
- `hospital`: 병원
- `pharmacy`: 약국
- `bank`: 은행
- `parking`: 주차장
- `gas_station`: 주유소
- `convenience_store`: 편의점

## 환경 변수
`GOOGLE_MAPS_API_KEY` 환경 변수가 필요합니다. `.env` 파일에 설정되어 있습니다.

## 스크립트 위치
`/Users/ldm/work/workspace/ai_agentic/opencode-demo/michael/.claude/skills/maps/scripts/`
