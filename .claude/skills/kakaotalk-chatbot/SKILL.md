---
name: kakaotalk-chatbot
description: |
  KakaoTalk Open Builder 챗봇 연동 스킬. 등록/설정/운영 가이드 + 제한사항.
  다음 키워드에 사용: "카카오톡", "카톡", "kakaotalk", "kakao", "챗봇", "오픈빌더", "open builder"
allowed-tools: Bash, Read, Write, Edit
---

# KakaoTalk Open Builder 챗봇 연동

KakaoTalk 채널 + Open Builder를 통해 AI 챗봇을 운영하는 스킬입니다.
Michael AI가 카카오톡 채널을 통해 사용자 메시지에 응답합니다.

## 아키텍처

```
[사용자 카카오톡 앱]
    ↓ 메시지 전송
[KakaoTalk 채널 (@michaelai)]
    ↓ Open Builder 라우팅
[폴백 블록 → MichaelAI 스킬]
    ↓ POST /api/kakao/skill (callbackUrl 포함)
[Michael HTTP Server (ngrok 터널)]
    ↓ 즉시 응답: useCallback: true + 대기 메시지
    ↓ 비동기: Claude AI 처리 → callbackUrl로 POST
[사용자에게 AI 답변 도착]
```

## 현재 설정 (Production)

| 항목 | 값 |
|------|-----|
| Kakao App ID | `1386108` |
| 채널 URL | `_jLxnzX` (`https://pf.kakao.com/_jLxnzX`) |
| 채널 검색 ID | `@michaelai` |
| Bot ID | `698dd7b4e9dbf31def3a1933` |
| Skill URL | `https://roxy-exoskeletal-shayla.ngrok-free.dev/api/kakao/skill` |
| AI 챗봇 모드 | ON (Callback API 활성화) |
| 콜백 쿼터 | 월 10만 건 |
| 챗봇 배포 버전 | v1.2 |

### .env 환경변수

```bash
KAKAO_APP_ID=1386108
KAKAO_REST_API_KEY=fe2594adfdeacf9c426fbdb73e8c7c59
KAKAO_JAVASCRIPT_KEY=18fa3203ccb7f4b109d83bc00f311b4e
KAKAO_NATIVE_APP_KEY=d44618a907098344fc0ea07b264bb574
KAKAO_CHANNEL_URL=_jLxnzX
KAKAO_CHANNEL_SEARCH_ID=@michaelai
KAKAO_BOT_ID=698dd7b4e9dbf31def3a1933
KAKAO_SKILL_URL=https://roxy-exoskeletal-shayla.ngrok-free.dev/api/kakao/skill
```

## 등록 과정 (처음부터 재현 가능)

### Step 1: Kakao Developers 앱 등록

1. https://developers.kakao.com/ 접속 → 로그인
2. **내 애플리케이션 → 애플리케이션 추가** 클릭
3. 앱 이름, 사업자명 입력 → 저장
4. 생성된 **앱 키** 확인: REST API 키, JavaScript 키, Native App 키

### Step 2: KakaoTalk 채널 생성

1. https://business.kakao.com/ 접속
2. **카카오톡 채널 → 새 채널 만들기**
3. 채널명, 검색용 아이디 설정 (예: `@michaelai`)
4. 프로필 이미지, 소개 작성

### Step 3: 채널 공개 설정 (필수!)

business.kakao.com 대시보드에서 **순서대로** 설정:

1. **공개 설정하기** → 채널 프로필 공개
2. **검색 허용하기** → 카카오톡에서 검색 가능
3. **채팅 사용하기** → 사용자와 채팅 가능

> **주의**: 반드시 공개 → 검색 → 채팅 순서로 설정해야 함. 채팅 먼저 켜면 "채널을 먼저 공개해 주세요" 에러 발생.

### Step 4: Open Builder 챗봇 생성

1. https://chatbot.kakao.com/ 접속
2. **챗봇 만들기** → 이름 입력 (예: MichaelAI)
3. **설정 → 챗봇 관리 → 카카오톡 채널 연결** → Step 2에서 만든 채널 선택

### Step 5: 스킬 서버 등록

1. **스킬 → 스킬 목록 → 생성**
2. 이름: `MichaelAI 응답`
3. URL: `https://<ngrok-domain>/api/kakao/skill`
4. Method: POST (기본값)
5. 저장

### Step 6: 폴백 블록에 스킬 연결

1. **시나리오 → 폴백 블록** 클릭
2. 봇 응답에서 **스킬 데이터 사용** 선택
3. Step 5에서 만든 스킬 선택
4. 저장

### Step 7: AI 챗봇 전환 + Callback API 활성화

> **핵심**: AI 챗봇 전환을 해야 Callback API (비동기 응답)를 사용할 수 있음.

1. **설정 → AI 챗봇 관리 → AI 챗봇 전환** 클릭
2. 목적, 사유 입력 → 신청
3. **즉시 승인됨** (문서에는 1-2영업일이라 하지만 실제 즉시)
4. 승인 후 상태: ON, 콜백 쿼터: 월 10만 건

### Step 8: 폴백 블록 Callback 설정

> **주의**: Callback 설정은 UI에서 숨겨져 있음!

1. **시나리오 → 폴백 블록** 편집
2. 블록 헤더 우측의 **kebab 메뉴 (⋮ 설정 버튼)** 클릭
3. 드롭다운에서 **"Callback 설정"** 선택
4. 토글: **꺼짐 → 켜짐**
5. 대기 메시지 입력: `생각하고 있어요... 잠시만 기다려주세요!`
6. 확인 → 블록 저장

### Step 9: 배포

1. **배포 → 배포하기**
2. 전체 배포 선택
3. 배포 메모 작성 → 배포
4. "배포가 완료되었습니다" 확인

## Callback API 플로우 (핵심)

### 왜 필요한가
- KakaoTalk 스킬 서버는 **5초 내** 응답해야 함
- Claude AI 응답은 10-60초 소요
- Callback API: 즉시 대기 메시지 반환 → 비동기로 AI 응답 전달 (최대 1분)

### 동작 과정

```
1. KakaoTalk → POST /api/kakao/skill
   Body: { userRequest: { utterance, callbackUrl, user: { id } } }

2. Server → 즉시 응답 (< 1초)
   { version: "2.0", useCallback: true, template: { outputs: [{ simpleText: { text: "생각하고 있어요... 🤔" } }] } }

3. Server → 비동기 처리
   Claude AI agent.chat(userId, utterance)

4. Server → POST callbackUrl
   { version: "2.0", template: { outputs: [{ simpleText: { text: "AI 응답 내용" } }] } }

5. 사용자 ← AI 답변 수신
```

### 구현 코드

**파일**: `src/core/http-server.ts`
- `handleKakaoSkill()` (line 425): 요청 수신 + Callback/Sync 분기
- `processKakaoCallback()` (line 497): 비동기 AI 처리 + callbackUrl POST
- `kakaoTextResponse()` (line 537): 응답 포맷 생성

**라우트**: `POST /api/kakao/skill` (line 185)

## 제한사항 (CRITICAL)

### 1. 능동적 메시지 발송 불가
- Open Builder 챗봇은 **사용자가 먼저 말을 걸어야만** 응답 가능
- 봇이 먼저 메시지를 보내는 것(push notification)은 **불가능**
- 능동적 알림이 필요하면 **알림톡/친구톡** 사용 (사업자등록 + 건당 과금 필요)
- **현재 Michael 구조**: Telegram = 능동 알림, KakaoTalk = 대화형 AI

### 2. Callback API 시간 제한
- Callback API 응답 제한: **최대 1분 (60초)**
- 1분 초과 시 사용자에게 응답이 전달되지 않음
- Claude AI 처리가 60초를 넘기면 실패 (복잡한 작업 시 주의)

### 3. 응답 길이 제한
- simpleText: **최대 1,000자**
- 1,000자 초과 시 truncate 처리 (`substring(0, 997) + '...'`)
- 긴 응답은 카드형(carousel)이나 링크로 분할 필요

### 4. Callback API 쿼터
- 월 **10만 건** 제한 (AI 챗봇 전환 시 기본 할당)
- 초과 시 Callback 사용 불가 → 동기 모드 fallback (5초 타임아웃)

### 5. 봇테스트 한계
- Open Builder의 **봇테스트**는 Callback API를 완전히 지원하지 않음
- 봇테스트에서는 대기 메시지만 표시되고 실제 AI 응답은 안 옴
- **실제 테스트는 KakaoTalk 앱에서만** 가능

### 6. ngrok 터널 의존
- 현재 ngrok free tier 사용 중
- ngrok 프로세스 종료 시 챗봇 응답 불가
- 재시작 시 도메인 유지됨 (`--domain` 플래그 사용)
- **상시 운영 필요**: `ngrok http 3000 --domain=roxy-exoskeletal-shayla.ngrok-free.dev`

### 7. 사용자 식별
- KakaoTalk은 실제 전화번호/이름 대신 **botUserKey** (해시 ID)를 전달
- 같은 사용자도 채널마다 다른 botUserKey를 가짐
- Michael 내부에서는 `kakao_<botUserKey>` 형식으로 userId 매핑

### 8. 응답 포맷 제한
- Open Builder 스킬 응답은 KakaoTalk 전용 JSON 포맷만 지원
- Markdown, HTML 렌더링 불가
- 지원 컴포넌트: simpleText, simpleImage, basicCard, listCard, carousel 등
- 현재는 simpleText만 사용 중

### 9. 동기 모드 제한 (Callback 없을 때)
- callbackUrl이 없는 요청은 **4.5초 내** 응답해야 함
- 타임아웃 시 "답변을 준비하는 중이에요" 메시지 반환
- AI 응답은 버려짐 (재시도 필요)

## 운영 가이드

### 서비스 시작/확인

```bash
# Michael 서비스 상태 확인
pm2 status michael

# ngrok 터널 시작 (별도 터미널)
ngrok http 3000 --domain=roxy-exoskeletal-shayla.ngrok-free.dev

# 로그 모니터링
pm2 logs michael --lines 20
```

### 로그에서 확인할 항목

```
💬 KakaoTalk skill request: "메시지" from <userId> (callback)  # 요청 수신
memory embeddings: query start                                   # AI 처리 시작
📤 KakaoTalk callback sent: 200 for "메시지"                    # 응답 전달 성공
⏰ KakaoTalk skill timeout for: "메시지"                        # 동기 모드 타임아웃
❌ KakaoTalk callback error: ...                                # 콜백 전달 실패
```

### 수동 테스트 (curl)

```bash
# Callback 모드 테스트
curl -s -X POST http://localhost:3000/api/kakao/skill \
  -H "Content-Type: application/json" \
  -d @- <<'EOF' | python3 -m json.tool
{
  "userRequest": {
    "utterance": "안녕 마이클!",
    "user": {"id": "test-user", "type": "botUserKey"},
    "callbackUrl": "https://httpbin.org/post"
  },
  "bot": {"id": "698dd7b4e9dbf31def3a1933"}
}
EOF

# 기대 응답: { "version": "2.0", "useCallback": true, ... }
```

### 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 챗봇 무응답 | ngrok 터널 중단 | `ngrok http 3000 --domain=...` 재시작 |
| "채팅이 불가능한 프로필" | 채널 공개/채팅 미설정 | business.kakao.com → 공개→검색→채팅 순서대로 |
| 대기 메시지만 표시 | Callback 미설정 또는 AI 처리 60초 초과 | 폴백 블록 Callback 설정 확인 |
| "답변 준비 중" 반복 | Callback 없이 동기 모드 | AI 챗봇 전환 + Callback 설정 확인 |
| 봇테스트에서 응답 안 옴 | 봇테스트는 Callback 미지원 | 실제 KakaoTalk 앱에서 테스트 |
| 응답 잘림 | 1,000자 초과 | 정상 (truncate 처리됨) |

## Telegram vs KakaoTalk 역할 분담

| 기능 | Telegram | KakaoTalk |
|------|----------|-----------|
| 능동적 알림 | O (sendMessage API) | X (불가) |
| 대화형 AI | O | O |
| 인라인 버튼 | O (inline_keyboard) | X (스킬 응답만) |
| 스케줄 알림 | O (cron → Gateway → Telegram) | X |
| PM/투자 알림 | O | X |
| 일반 대화 | O | O |
| 접근성 (한국) | 낮음 (앱 설치 필요) | 높음 (기본 설치) |

**결론**: Telegram은 **능동적 알림 + 풀기능**, KakaoTalk은 **한국 사용자 접근성 + 대화형 AI**

## 향후 개선 가능

1. **응답 포맷 다양화**: simpleText → basicCard, carousel 등으로 리치 응답
2. **알림톡 연동**: 사업자등록 후 능동적 알림 가능 (건당 ~8원)
3. **빠른 응답 캐시**: 자주 묻는 질문 캐싱으로 동기 모드에서도 응답
4. **멀티턴 대화**: 컨텍스트 블록으로 대화 흐름 관리
5. **ngrok → 고정 도메인**: production 서버 직접 노출 또는 Cloudflare Tunnel
