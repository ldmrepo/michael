# ngrok 설정 가이드

Michael HTTP 서버를 외부에서 접근하기 위한 ngrok 터널 설정 방법입니다.

## 사전 준비

### 1. ngrok 설치

```bash
# macOS
brew install ngrok

# 또는 https://ngrok.com/download 에서 직접 다운로드
```

### 2. 인증 토큰 설정

```bash
# https://dashboard.ngrok.com/get-started/your-authtoken 에서 토큰 확인
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

## 실행 방법

### 1. Michael 서버 시작

```bash
pnpm dev
```

### 2. ngrok 터널 시작

```bash
# 고정 dev 도메인 사용 (무료)
ngrok http 3000 --url=roxy-exoskeletal-shayla.ngrok-free.dev

# 또는 랜덤 URL 사용
ngrok http 3000
```

### 3. 백그라운드 실행

```bash
ngrok http 3000 --url=roxy-exoskeletal-shayla.ngrok-free.dev > /tmp/ngrok.log 2>&1 &
```

## 접속 확인

```bash
# Health Check
curl -H "ngrok-skip-browser-warning: true" https://roxy-exoskeletal-shayla.ngrok-free.dev/health

# Agent Card
curl -H "ngrok-skip-browser-warning: true" https://roxy-exoskeletal-shayla.ngrok-free.dev/.well-known/agent.json

# Mini App (브라우저)
open https://roxy-exoskeletal-shayla.ngrok-free.dev/webapp/
```

## 엔드포인트 목록

| 엔드포인트 | URL |
|-----------|-----|
| Health | https://roxy-exoskeletal-shayla.ngrok-free.dev/health |
| Agent Card | https://roxy-exoskeletal-shayla.ngrok-free.dev/.well-known/agent.json |
| Mini App | https://roxy-exoskeletal-shayla.ngrok-free.dev/webapp/ |
| Session API | https://roxy-exoskeletal-shayla.ngrok-free.dev/api/webapp/session/:id |

## 트러블슈팅

### ERR_NGROK_334: Endpoint already online

동일한 URL로 다른 세션이 실행 중입니다.

```bash
# 기존 ngrok 프로세스 종료
pkill -9 ngrok

# 또는 대시보드에서 중지
# https://dashboard.ngrok.com/endpoints
```

### ERR_NGROK_313: Paid plan required

무료 플랜에서는 커스텀 서브도메인 사용 불가. `.ngrok-free.dev` 도메인만 사용 가능.

### 브라우저 경고 페이지

curl 요청 시 ngrok 경고 페이지가 표시되면:

```bash
curl -H "ngrok-skip-browser-warning: true" <URL>
```

## 참고 링크

- [ngrok 대시보드](https://dashboard.ngrok.com)
- [ngrok 문서](https://ngrok.com/docs)
- [무료 고정 도메인 안내](https://ngrok.com/blog/free-static-domains-ngrok-users)
