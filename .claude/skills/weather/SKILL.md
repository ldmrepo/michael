---
name: weather
description: |
  날씨 정보 조회 스킬. 현재 날씨, 기온, 예보 확인.
  다음 질문에 사용: "날씨", "weather", "기온", "온도", "비", "눈", "예보", "오늘 날씨", "내일 날씨"
allowed-tools: Bash(curl:*), WebFetch, WebSearch
---

# 날씨 조회 스킬

사용자에게 날씨 정보를 제공합니다.

## 사용 방법

1. 사용자가 위치를 지정하면 해당 지역 날씨 조회
2. 위치를 지정하지 않으면 "서울" 기본값 사용
3. "내일", "이번주" 등 기간 지정 시 예보 제공

## API 활용

Open-Meteo API (무료, API 키 불필요):
```bash
# 서울 날씨 (위도 37.5665, 경도 126.9780)
curl "https://api.open-meteo.com/v1/forecast?latitude=37.5665&longitude=126.9780&current=temperature_2m,weathercode,windspeed_10m,relative_humidity_2m&daily=weathercode,temperature_2m_max,temperature_2m_min&timezone=Asia/Seoul"
```

### 주요 도시 좌표
- 서울: 37.5665, 126.9780
- 부산: 35.1796, 129.0756
- 대구: 35.8714, 128.6014
- 인천: 37.4563, 126.7052
- 광주: 35.1595, 126.8526
- 대전: 36.3504, 127.3845
- 제주: 33.4996, 126.5312

### Weather Code 해석
- 0: 맑음 ☀️
- 1-3: 구름 조금/많음 ⛅
- 45, 48: 안개 🌫️
- 51-55: 이슬비 🌧️
- 61-65: 비 🌧️
- 71-75: 눈 ❄️
- 80-82: 소나기 🌦️
- 95: 뇌우 ⛈️

## 응답 형식

```
*서울 현재 날씨* ☀️

🌡️ 기온: 5°C
💨 바람: 12 km/h
💧 습도: 45%

*주간 예보*
• 내일: 맑음 -2°C ~ 7°C
• 모레: 구름 많음 0°C ~ 8°C
```

## 참고사항
- Telegram 마크다운 형식 사용 (*bold*, _italic_)
- 이모지로 날씨 상태 시각화
- 체감온도, 미세먼지 등 추가 정보는 WebSearch 활용