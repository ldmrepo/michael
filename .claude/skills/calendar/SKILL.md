---
name: calendar
description: |
  Google Calendar 연동 스킬. 일정 조회, 생성, 수정, 삭제.
  다음 키워드에 사용: "일정", "캘린더", "calendar", "스케줄", "schedule", "약속", "미팅", "회의"
allowed-tools: Bash(python3:*), Read, Write
---

# Google Calendar Integration

Google Calendar API를 통해 일정을 조회, 생성, 수정하는 스킬입니다.

## Prerequisites

1. Python 3.10+
2. Google Cloud 프로젝트에서 Google Calendar API 활성화
3. OAuth 2.0 credentials (`credentials.json`)
4. 필요 패키지: `google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib`

## OAuth Setup

Gmail 스킬과 동일한 credentials.json을 공유합니다.

Calendar 스코프가 추가로 필요합니다:
- `https://www.googleapis.com/auth/calendar` - 캘린더 전체 접근
- `https://www.googleapis.com/auth/calendar.readonly` - 읽기 전용
- `https://www.googleapis.com/auth/calendar.events` - 이벤트만

## 사용 방법

### 일정 목록 조회

```bash
# 오늘 일정
python3 scripts/list_events.py

# 다음 7일 일정
python3 scripts/list_events.py --days 7

# 특정 날짜 범위
python3 scripts/list_events.py --start "2024-01-01" --end "2024-01-31"

# JSON 출력
python3 scripts/list_events.py --json
```

### 일정 생성

```bash
# 기본 일정 생성
python3 scripts/create_event.py --title "회의" --start "2024-01-15 14:00" --end "2024-01-15 15:00"

# 종일 일정
python3 scripts/create_event.py --title "휴가" --date "2024-01-20" --all-day

# 장소 및 설명 포함
python3 scripts/create_event.py --title "미팅" \
  --start "2024-01-15 10:00" --end "2024-01-15 11:00" \
  --location "서울시 강남구" \
  --description "프로젝트 킥오프 미팅"

# 참석자 추가
python3 scripts/create_event.py --title "팀 회의" \
  --start "2024-01-15 14:00" --end "2024-01-15 15:00" \
  --attendees "person1@example.com,person2@example.com"
```

### 일정 상세 조회

```bash
python3 scripts/get_event.py <event_id>
```

### 일정 삭제

```bash
python3 scripts/delete_event.py <event_id>
```

## 스크립트 위치

모든 스크립트는 `scripts/` 디렉토리에 있습니다:
- `calendar_auth.py` - 인증 유틸리티
- `list_events.py` - 일정 목록 조회
- `create_event.py` - 일정 생성
- `get_event.py` - 일정 상세 조회
- `delete_event.py` - 일정 삭제

## Credentials 설정

Gmail 스킬의 credentials.json을 공유하거나, 별도로 다운로드:

```bash
# Gmail 스킬 credentials 심볼릭 링크
ln -s ../gmail-integration/credentials.json credentials.json
```

또는 환경변수:
```bash
export CALENDAR_CREDENTIALS_PATH=/path/to/credentials.json
```

## 응답 형식

### 일정 조회 응답

```
📅 오늘의 일정 (2024년 1월 15일)

1. 09:00-10:00 | 아침 미팅
   📍 회의실 A

2. 14:00-15:00 | 프로젝트 회의
   📍 Zoom
   👥 3명 참석

총 2개의 일정이 있습니다.
```

### 일정 생성 응답

```
✅ 일정이 생성되었습니다!

📅 프로젝트 킥오프
📆 2024년 1월 15일 14:00-15:00
📍 서울시 강남구

🔗 https://calendar.google.com/calendar/event?eid=...
```

## API 제한 사항

- 기본 캘린더: "primary" (사용자의 기본 캘린더)
- 시간대: 시스템 시간대 자동 사용
- 반복 일정: 현재 단일 일정만 지원

## 보안 참고

- `credentials.json` - OAuth 클라이언트 시크릿 (버전 관리 제외)
- `token.json` - 액세스 토큰 (버전 관리 제외)
- `.gitignore`에 추가 필수
