# Moltbot 메모리 시스템 의존성 분석

## 현재 마이클의 의존성

```json
{
  "dependencies": {
    "@anthropic-ai/sdk": "^0.32.1",
    "better-sqlite3": "^11.7.0",     // ⚠️ Moltbot은 node:sqlite 사용
    "dotenv": "^16.4.7",
    "telegraf": "^4.16.3",
    "ws": "^8.18.0",
    "node-cron": "^3.0.3",
    "chokidar": "^4.0.3"              // ⚠️ 버전 업데이트 필요
  }
}
```

## 추가 필요한 의존성

### 1. sqlite-vec (필수)
벡터 검색을 위한 SQLite 확장

```bash
pnpm add sqlite-vec@0.1.7-alpha.2
```

**사용 목적:**
- SQLite에 벡터 검색 기능 추가
- `vec0` virtual table 지원
- 코사인 유사도 검색

### 2. node-llama-cpp (선택)
로컬 임베딩 모델 실행

```bash
pnpm add -D node-llama-cpp@3.15.0
```

**사용 목적:**
- API 키 없이 로컬에서 임베딩 생성
- 무료 (CPU/GPU 사용)
- 오프라인 사용 가능

**참고:**
- `optionalDependencies`로 설치
- 설치 실패해도 프로젝트 동작 (OpenAI/Gemini API 사용 가능)
- 크기가 큼 (~수백 MB with 모델 파일)

### 3. chokidar 버전 업데이트 (권장)

```bash
pnpm add chokidar@^5.0.0
```

**이유:**
- Moltbot은 5.0.0 사용
- 4.0.3도 동작하지만 최신 버전이 안정적

## 제거 검토 대상

### better-sqlite3

**Moltbot의 접근:**
- Node.js 22+ 내장 `node:sqlite` 사용
- 외부 의존성 없음
- 더 가벼움

**마이그레이션 전략:**
1. **Phase 1-3**: better-sqlite3 유지 (호환성)
2. **Phase 4 이후**: node:sqlite로 전환
3. 기존 코드가 better-sqlite3에 의존하면 점진적 마이그레이션

## 설치 명령어

### 1단계: 필수 의존성 추가

```bash
cd /Users/ldm/work/workspace/ai_agentic/opencode-demo/michael
pnpm add sqlite-vec@0.1.7-alpha.2
pnpm add chokidar@^5.0.0
```

### 2단계: 로컬 임베딩 지원 (선택)

```bash
pnpm add -D node-llama-cpp@3.15.0
```

**주의:**
- 설치 시간이 오래 걸릴 수 있음 (~5-10분)
- 네이티브 모듈 컴파일 필요
- 실패해도 프로젝트는 동작 (API 사용)

## 의존성 트리

```
마이클 메모리 시스템
├── sqlite-vec          # 벡터 검색 (필수)
├── chokidar           # 파일 워칭 (필수)
├── node-llama-cpp     # 로컬 임베딩 (선택)
└── node:sqlite        # Node.js 내장 (22+)
    └── better-sqlite3 # 기존 (마이그레이션 후 제거)
```

## 임베딩 Provider 옵션

### 1. 로컬 모델 (추천 - 무료)

```typescript
{
  provider: 'local',
  local: {
    modelPath: '~/.michael/models/embedding-model.gguf'
  }
}
```

**장점:**
- ✅ API 키 불필요
- ✅ 무료
- ✅ 오프라인 작동
- ✅ 프라이버시 (데이터가 외부로 나가지 않음)

**단점:**
- ⚠️ 초기 모델 다운로드 필요 (~500MB-2GB)
- ⚠️ CPU/GPU 리소스 사용
- ⚠️ 속도가 API보다 느릴 수 있음

### 2. OpenAI API (선택)

```typescript
{
  provider: 'openai',
  model: 'text-embedding-3-small',
  remote: {
    apiKey: process.env.OPENAI_API_KEY
  }
}
```

**장점:**
- ✅ 빠름
- ✅ 고품질 임베딩
- ✅ 설정 간단

**단점:**
- ❌ API 키 필요
- ❌ 비용 발생 (~$0.0001 per 1K tokens)
- ❌ 인터넷 필요

### 3. Gemini API (선택)

```typescript
{
  provider: 'gemini',
  model: 'text-embedding-004',
  remote: {
    apiKey: process.env.GOOGLE_API_KEY
  }
}
```

**장점/단점:**
- OpenAI와 유사
- Google AI Studio에서 무료 tier 제공 (일일 제한)

## 다음 단계

Task #2: Moltbot 메모리 핵심 파일 이식
- 의존성 설치 후 파일 복사 시작
- import 경로 수정
- 타입 호환성 확인
