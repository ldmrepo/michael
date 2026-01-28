# Anthropic API vs Claude Code CLI

## 테스트 결과 요약

### ❌ @anthropic-ai/sdk (API 키 필요)
- **요구사항**: ANTHROPIC_API_KEY 환경 변수
- **Claude Max 구독**: 사용 불가 ❌
- **비용**: 사용량 기반 과금 (별도)

### ✅ Claude Code CLI (API 키 불필요)
- **요구사항**: claude.ai 계정 (Claude Max 구독 포함)
- **Claude Max 구독**: 사용 가능 ✅
- **비용**: 월 구독료에 포함

## 차이점 비교표

| 항목 | Claude Max | Anthropic API |
|------|-----------|---------------|
| **타입** | 웹 인터페이스 구독 | API 서비스 |
| **가격** | $20/월 (Pro) 또는 $200/월 (Max) | 사용량 기반 |
| **인증** | claude.ai 계정 | API 키 |
| **Claude Code CLI** | ✅ 작동 | ✅ 작동 |
| **@anthropic-ai/sdk** | ❌ 불가 | ✅ 작동 |
| **웹 인터페이스** | ✅ 무제한 | ❌ 없음 |

## 통합 테스트 결과

```bash
$ npx tsx test-integration.ts

🧪 Integration Test: Claude Code Agent

1️⃣ Initializing Memory...
✅ Memory initialized

2️⃣ Initializing Agent...
✅ Agent initialized

3️⃣ Testing chat...
✅ Chat successful!
Response: Hello from Michael!

4️⃣ Checking memory...
✅ Found 2 messages in memory

5️⃣ Cleaning up...
✅ Cleanup complete

🎉 Integration test complete!
```

## 권장사항

### Claude Max 사용자 (현재 상황)

**✅ 추천: Claude Code CLI 사용**
- API 키 불필요
- 이미 구현된 `src/agent/claude-code.ts` 사용
- 추가 비용 없음

**구현 완료:**
- ✅ Claude Code CLI 통합 (`-p` 모드)
- ✅ stdin/stdout 방식 통신
- ✅ 메모리 컨텍스트 로딩
- ✅ Fact/Schedule 자동 추출

### API 키를 사용하려는 경우

**API 키 발급:**
1. https://console.anthropic.com/ 접속
2. API 키 생성
3. `.env`에 `ANTHROPIC_API_KEY` 설정

**장점:**
- 더 빠른 응답 속도
- 프로그래밍 방식 제어
- 프로덕션 환경에 적합

**단점:**
- 추가 비용 발생
- 사용량 제한 관리 필요

## 마이클 프로젝트에 미치는 영향

### 현재 구현 (Claude Code CLI)

**작동 방식:**
```typescript
// src/agent/claude-code.ts
const process = spawn('claude', ['-p']);
process.stdin.write(prompt);
process.stdin.end();

// 응답은 stdout으로 받음
process.stdout.on('data', (data) => {
  stdout += data.toString();
});
```

**장점:**
- ✅ 즉시 사용 가능 (API 키 불필요)
- ✅ Claude Max 구독으로 충분
- ✅ 안정적 (Claude.ai 인프라 사용)

**단점:**
- ⚠️ 프로세스 오버헤드
- ⚠️ 응답 속도가 API보다 느릴 수 있음

### 대안 구현 (@anthropic-ai/sdk)

**필요 사항:**
- Anthropic API 키
- 추가 비용

**변경 필요:**
```typescript
// src/agent/anthropic.ts (새 파일)
import Anthropic from '@anthropic-ai/sdk';

const client = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

const response = await client.messages.create({
  model: 'claude-sonnet-4-5',
  max_tokens: 2048,
  messages: [{ role: 'user', content: prompt }]
});
```

## 결론

**Claude Max 사용자는 Claude Code CLI를 계속 사용하는 것이 권장됩니다.**

- ✅ 추가 비용 없음
- ✅ 즉시 사용 가능
- ✅ 안정적으로 작동
- ✅ 구현 완료

API가 필요한 경우에만 @anthropic-ai/sdk로 전환을 고려하세요.
