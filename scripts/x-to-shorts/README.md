# X(Twitter) 트렌드 기반 Shorts 아이디어 생성기

X(Twitter)에서 바이럴/트렌딩 트윗을 수집하고 분석하여 YouTube Shorts 콘텐츠 아이디어를 자동 생성하는 시스템입니다.

## 목차

- [개요](#개요)
- [파이프라인 구조](#파이프라인-구조)
- [설치 및 요구사항](#설치-및-요구사항)
- [빠른 시작](#빠른-시작)
- [사용법](#사용법)
  - [테스트 실행](#테스트-실행)
  - [JSON 파일 입력](#json-파일-입력)
  - [X 검색 연동](#x-검색-연동)
  - [자동 영상 생성](#자동-영상-생성)
- [바이럴 분석기](#바이럴-분석기)
- [아이디어 변환기](#아이디어-변환기)
- [템플릿 유형](#템플릿-유형)
- [X 검색 쿼리 가이드](#x-검색-쿼리-가이드)
- [출력 형식](#출력-형식)
- [Telegram 연동](#telegram-연동)
- [비용 안내](#비용-안내)
- [문제 해결](#문제-해결)

---

## 개요

이 도구는 X(Twitter)에서 인기 있는 트윗을 분석하여 YouTube Shorts 콘텐츠 아이디어로 변환합니다.

**핵심 기능:**
- 트윗 바이럴 잠재력 점수 계산 (0-100)
- 감정/주제 자동 분석
- 4가지 템플릿 유형 자동 추천
- agentic_video.py와 연동하여 영상 자동 생성

---

## 파이프라인 구조

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  X 트렌딩 수집   │ → │   바이럴 분석    │ → │  아이디어 변환   │ → │  영상 생성      │ → │  텍스트 후처리   │
│   Playwright    │    │ viral_analyzer  │    │ idea_transformer│    │ agentic_video   │    │ text_overlay    │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
        ↓                      ↓                      ↓                      ↓                      ↓
   트윗 JSON            바이럴 점수/감정        Shorts 아이디어         텍스트 없는 영상      최종 영상
                        주제/밈잠재력          + 텍스트 오버레이 설정   (Veo 3.1)            + 한글 텍스트
```

### 텍스트 안전 워크플로우

AI 영상 생성 시 텍스트 오류를 방지하는 권장 워크플로우:

```
1. 프롬프트 생성 시 "no text" 지시어 자동 추가
                ↓
2. Veo 3.1로 텍스트 없는 순수 영상 생성
                ↓
3. FFmpeg로 정확한 한글 텍스트 오버레이 적용
                ↓
4. 최종 영상 출력
```

---

## 설치 및 요구사항

### 필수 요구사항
- Python 3.10+
- Claude CLI (`claude` 명령어)

### 선택 요구사항 (영상 생성 시)
- FFmpeg
- Google Cloud 계정 (Veo 3.1 API)

### 파일 구조
```
scripts/x-to-shorts/
├── README.md                   # 이 문서
├── generate_from_x.py          # 메인 파이프라인
├── viral_analyzer.py           # 바이럴 분석 엔진
├── idea_transformer.py         # 아이디어 변환기
├── prompt_sanitizer.py         # 텍스트 안전 프롬프트 생성기
├── text_overlay.py             # FFmpeg 텍스트 오버레이 도구
├── video_postprocessor.py      # 영상 후처리 파이프라인
└── templates/
    ├── reaction.json           # 반응형 템플릿
    ├── tutorial.json           # 정보형 템플릿
    ├── story.json              # 스토리형 템플릿
    └── aesthetic.json          # 감성형 템플릿
```

---

## 빠른 시작

```bash
# 1. 테스트 실행 (샘플 데이터)
python3 scripts/x-to-shorts/generate_from_x.py --test

# 2. 바이럴 분석기 단독 테스트
python3 scripts/x-to-shorts/viral_analyzer.py --test

# 3. 아이디어 변환기 단독 테스트
python3 scripts/x-to-shorts/idea_transformer.py --test
```

---

## 사용법

### 테스트 실행

샘플 트윗 데이터로 전체 파이프라인을 테스트합니다.

```bash
python3 scripts/x-to-shorts/generate_from_x.py --test
```

### JSON 파일 입력

트윗 데이터가 담긴 JSON 파일을 입력으로 사용합니다.

```bash
# 기본 사용
python3 scripts/x-to-shorts/generate_from_x.py \
  --input tweets.json \
  --count 5

# 상세 출력
python3 scripts/x-to-shorts/generate_from_x.py \
  --input tweets.json \
  --count 5 \
  --verbose

# 드라이런 (분석만, 저장 안함)
python3 scripts/x-to-shorts/generate_from_x.py \
  --input tweets.json \
  --dry-run
```

**트윗 JSON 형식:**
```json
[
  {
    "tweet_id": "1234567890",
    "text": "트윗 내용",
    "author": "@username",
    "retweets": 5000,
    "likes": 12000,
    "replies": 300,
    "media": ["image_url"],
    "hashtags": ["#태그1", "#태그2"],
    "url": "https://x.com/username/status/1234567890"
  }
]
```

### X 검색 연동

X 검색 쿼리를 지정하여 실시간 트렌딩 트윗을 수집합니다.

> **참고:** 실제 X 검색은 Playwright MCP를 통한 브라우저 자동화가 필요합니다.

```bash
python3 scripts/x-to-shorts/generate_from_x.py \
  --query "lang:ko min_retweets:1000" \
  --count 5
```

### 자동 영상 생성

가장 점수가 높은 아이디어로 바로 영상을 생성합니다.

```bash
python3 scripts/x-to-shorts/generate_from_x.py \
  --input tweets.json \
  --auto-generate \
  --output /tmp/shorts
```

### 전체 옵션

| 옵션 | 단축 | 설명 | 기본값 |
|------|------|------|--------|
| `--query` | `-q` | X 검색 쿼리 | - |
| `--input` | `-i` | 트윗 JSON 파일 경로 | - |
| `--count` | `-c` | 분석할 트윗 수 | 5 |
| `--output` | `-o` | 출력 디렉토리 | /tmp/x-to-shorts |
| `--auto-generate` | `-a` | 자동 영상 생성 | false |
| `--dry-run` | `-d` | 드라이런 (분석만) | false |
| `--verbose` | `-v` | 상세 출력 | false |
| `--test` | `-t` | 샘플 데이터 테스트 | false |
| `--json` | - | JSON 형식 출력 | false |

---

## 바이럴 분석기

`viral_analyzer.py`는 트윗의 바이럴 잠재력을 분석합니다.

### 분석 요소 및 가중치

| 요소 | 가중치 | 설명 |
|------|--------|------|
| 참여율 | 30% | (RT + Like + Reply) / 기준치 |
| 감정 강도 | 25% | 긍정/부정/놀라움 지수 |
| 밈 잠재력 | 20% | 반복 가능한 포맷인가 |
| 시각 요소 | 15% | 이미지/영상 포함 여부 |
| 시의성 | 10% | 현재 트렌드와 연관성 |

### 감정 분류

| 감정 | 키워드 예시 |
|------|------------|
| surprise | 헐, 대박, 미쳤, 충격, 실화, ㅋㅋㅋ |
| joy | 행복, 기쁘, 좋아, 귀여, 힐링, 웃기 |
| anger | 화나, 짜증, 열받, 답답, 최악 |
| curiosity | 궁금, 왜, 어떻게, 비밀, 꿀팁 |
| neutral | 기타 |

### 주제 태그

AI, Tech, Gaming, Entertainment, Daily, Food, Travel, Finance, Health, Beauty, General

### 단독 사용

```bash
# 테스트
python3 scripts/x-to-shorts/viral_analyzer.py --test

# JSON 파일 분석
python3 scripts/x-to-shorts/viral_analyzer.py \
  --input tweets.json \
  --output analysis.json

# JSON 출력
python3 scripts/x-to-shorts/viral_analyzer.py \
  --input tweets.json \
  --json
```

---

## 아이디어 변환기

`idea_transformer.py`는 분석된 트윗을 Shorts 아이디어로 변환합니다.

### 생성 요소

- **브리프(brief)**: 영상 아이디어 한 문장 요약
- **훅(hook)**: 첫 3초 시청자 주목 문구
- **구조(structure)**: 영상 전개 방식
- **핵심 비주얼**: 주요 장면 아이디어
- **오디오 제안**: 배경음악/효과음 가이드
- **해시태그**: 추천 태그 목록

### 단독 사용

```bash
# 테스트
python3 scripts/x-to-shorts/idea_transformer.py --test

# 단일 트윗 변환
python3 scripts/x-to-shorts/idea_transformer.py \
  --tweet "헐 이거 실화냐 대박" \
  --template reaction \
  --json
```

---

## 템플릿 유형

### 1. 반응형 (Reaction)

**특징:** "이거 실화냐" 류의 충격/반응 콘텐츠

| 항목 | 내용 |
|------|------|
| 훅 형식 | "헐, {핵심} 실화냐?" |
| 구조 | 문제제시 → 반응 → 해설 |
| 비주얼 | 빠른 줌, 점프컷, 밈 스타일 |
| 적합 감정 | surprise, curiosity |

### 2. 정보형 (Tutorial)

**특징:** "꿀팁" 류의 정보/노하우 전달 콘텐츠

| 항목 | 내용 |
|------|------|
| 훅 형식 | "이거 모르면 손해! {주제}" |
| 구조 | 문제 → 해결책 → 결과 |
| 비주얼 | 깔끔한 시연, 단계별 진행 |
| 적합 감정 | curiosity |

### 3. 스토리형 (Story)

**특징:** 일상 에피소드, 스토리텔링 콘텐츠

| 항목 | 내용 |
|------|------|
| 훅 형식 | "어제 {상황}했는데..." |
| 구조 | 상황 → 전개 → 반전 |
| 비주얼 | 브이로그 스타일, POV 샷 |
| 적합 감정 | joy, surprise, neutral |

### 4. 감성형 (Aesthetic)

**특징:** 비주얼 중심, 힐링/감성 콘텐츠

| 항목 | 내용 |
|------|------|
| 훅 형식 | "{장면}의 순간" |
| 구조 | 장면1 → 장면2 → 마무리 |
| 비주얼 | 시네마틱, 슬로우모션, ASMR |
| 적합 감정 | joy, neutral |

---

## X 검색 쿼리 가이드

### 추천 검색 쿼리

| 목적 | 쿼리 |
|------|------|
| 한국어 바이럴 | `lang:ko min_retweets:1000 -filter:replies` |
| 특정 주제 트렌딩 | `#AI min_faves:500` |
| 유머/밈 콘텐츠 | `lang:ko min_retweets:2000 (짤 OR 웃긴 OR ㅋㅋ)` |
| 정보/팁 콘텐츠 | `lang:ko (꿀팁 OR 팁) min_faves:1000` |
| 감성 콘텐츠 | `lang:ko (힐링 OR 감성) filter:images` |

### 검색 연산자

| 연산자 | 설명 | 예시 |
|--------|------|------|
| `min_retweets:` | 최소 리트윗 수 | `min_retweets:1000` |
| `min_faves:` | 최소 좋아요 수 | `min_faves:5000` |
| `lang:` | 언어 필터 | `lang:ko` |
| `from:` | 특정 사용자 | `from:elonmusk` |
| `since:` / `until:` | 날짜 범위 | `since:2024-01-01` |
| `-filter:replies` | 답글 제외 | |
| `filter:images` | 이미지 포함 | |
| `filter:videos` | 비디오 포함 | |

---

## 출력 형식

### ideas.json 구조

```json
{
  "source_tweet": {
    "id": "트윗 ID",
    "text": "원본 트윗 내용",
    "author": "@username",
    "url": "https://x.com/...",
    "retweets": 5000,
    "likes": 12000
  },
  "analysis": {
    "viral_score": 88,
    "engagement_score": 75.5,
    "emotion": "surprise",
    "emotion_intensity": 0.8,
    "themes": ["AI", "Tech"],
    "meme_potential": "high",
    "visual_content": true,
    "timeliness": "trending",
    "recommendation": "강력 추천",
    "suggested_template": "reaction"
  },
  "idea": {
    "source_tweet": "https://x.com/...",
    "source_text": "원본 트윗",
    "brief": "영상 아이디어 요약",
    "viral_score": 88,
    "template_type": "reaction",
    "hook": "첫 3초 훅",
    "structure": "문제제시 → 반응 → 해설",
    "key_visual": "핵심 비주얼 설명",
    "audio_suggestion": "오디오 가이드",
    "hashtags": ["#shorts", "#AI"],
    "estimated_duration": 60
  },
  "project_plan": {
    "brief": "영상 브리프",
    "continuity": { ... },
    "beat_sheet": { ... },
    "shots": [ ... ]
  }
}
```

### project_plan.json (agentic_video 호환)

```json
{
  "brief": "영상 브리프",
  "continuity": {
    "color_palette": "high contrast, vibrant colors",
    "lighting_setup": "dramatic rim lighting",
    "camera_style": "dynamic zooms and push-ins",
    "audio_theme": "tension building with surprise reveal"
  },
  "beat_sheet": {
    "hook": "충격적인 오프닝",
    "setup": "상황 설명",
    "development": "전개",
    "climax": "클라이맥스",
    "resolution": "마무리"
  },
  "shots": [
    {
      "id": 1,
      "subject": "피사체",
      "emotion": "감정",
      "optics": "샷 타입",
      "motion": "카메라 움직임",
      "lighting": "조명",
      "style": "스타일",
      "audio": "오디오",
      "continuity": "연속성",
      "duration": 8
    }
  ]
}
```

---

## Telegram 연동

Michael 봇을 통해 자연어로 사용할 수 있습니다.

### 아이디어 생성

```
User: "X 트렌드 쇼츠 아이디어 5개"

Michael:
🔥 X 트렌딩 분석 중...
📊 바이럴 트윗 5개 발견

1. [바이럴 점수: 92] 반응형
   원본: "AI가 그린 고양이 사진인데..."
   → 쇼츠 아이디어: AI 그림 vs 실제 비교 리액션

2. [바이럴 점수: 87] 스토리형
   원본: "출근하다가 로봇 배달원 만났는데..."
   → 쇼츠 아이디어: 일상 속 로봇 목격담

🎬 영상으로 만들까요? (번호 선택)
```

### 영상 생성

```
User: "2번으로 쇼츠 만들어줘"

Michael:
🎬 '일상 속 로봇 목격담' 쇼츠 제작 시작

1. Beat Sheet 생성 중...
2. Shot List 구성 중... (7 shots)
3. Veo 3.1 영상 생성 중...
   - Clip 1/7 완료 ✅
   - Clip 2/7 완료 ✅
   ...
4. FFmpeg 합성 중...

✅ 완료! 총 52초 영상
📤 YouTube 업로드할까요?
```

---

## 텍스트 오버레이 시스템

### 문제: AI 영상의 텍스트 오류

Veo 3.1 등 AI 영상 생성 모델은 텍스트 렌더링에 약점이 있습니다:
- 한글 텍스트 왜곡
- 의도치 않은 자막 생성
- 간판/로고 텍스트 오류

### 해결: 텍스트 분리 전략

1. **프롬프트 안전화** (`prompt_sanitizer.py`)
   - "no text" 지시어 자동 추가
   - 텍스트 위험 장면 감지 및 경고
   - 대사 추출 및 분리

2. **후처리 오버레이** (`text_overlay.py`)
   - FFmpeg 기반 정확한 한글 텍스트 렌더링
   - 다양한 스타일 프리셋 (hook, subtitle, caption, hashtag)
   - 페이드/팝/슬라이드 애니메이션

### 텍스트 오버레이 사용법

```bash
# 단일 텍스트 추가
python3 scripts/x-to-shorts/text_overlay.py \
  --video input.mp4 \
  --text "헐, 실화냐?" \
  --style hook \
  --start 0.5 \
  --end 3.0

# JSON 설정 파일 사용
python3 scripts/x-to-shorts/text_overlay.py \
  --video input.mp4 \
  --config overlays.json

# 스타일 목록 확인
python3 scripts/x-to-shorts/text_overlay.py --list-styles
```

### 텍스트 스타일 프리셋

| 스타일 | 설명 | 용도 |
|--------|------|------|
| `hook` | 크고 강렬한 노란색 | 첫 3초 훅 |
| `subtitle` | 하단 흰색 자막 | 대사/설명 |
| `caption` | 상단 정보 표시 | 부가 정보 |
| `hashtag` | 하단 좌측 시안색 | 해시태그 |
| `emphasis` | 빨간색 강조 | 중요 포인트 |
| `minimal` | 연한 흰색 | 감성형 영상 |

### 위치 옵션

```
top         top_left      top_right
center      center_left   center_right
bottom      bottom_left   bottom_right
```

### 영상 후처리 파이프라인

```bash
# 프로젝트 플랜에서 오버레이 적용
python3 scripts/x-to-shorts/video_postprocessor.py \
  --video final.mp4 \
  --plan project_plan.json

# 일괄 처리
python3 scripts/x-to-shorts/video_postprocessor.py \
  --batch /tmp/shorts \
  --plan project_plan.json
```

### 오버레이 설정 JSON 형식

```json
{
  "overlays": [
    {
      "text": "헐, 이거 실화?",
      "start_time": 0.5,
      "end_time": 3.0,
      "style": "hook",
      "position": "center",
      "animation": "pop"
    },
    {
      "text": "#shorts #유튜브쇼츠",
      "start_time": 56.0,
      "end_time": 59.7,
      "style": "hashtag",
      "position": "bottom_left",
      "animation": "slide"
    }
  ]
}
```

---

## 비용 안내

### Veo 3.1 영상 생성 비용

| 모델 | 초당 비용 | 60초 영상 |
|------|----------|----------|
| Standard | $0.40 | $24.00 |
| Fast | $0.15 | $9.00 |

**환경변수로 모델 선택:**
```bash
export VEO_MODEL=veo-3.1-generate-preview        # Standard (기본)
export VEO_MODEL=veo-3.1-fast-generate-preview   # Fast (저렴)
```

### 무료 기능

- 트윗 수집 (Playwright)
- 바이럴 분석
- 아이디어 생성
- 프로젝트 플랜 생성

---

## 문제 해결

### Claude CLI를 찾을 수 없음

```
⚠️ Claude CLI not found
```

**해결:** Claude CLI가 설치되어 있고 PATH에 있는지 확인
```bash
which claude
claude --version
```

### X 검색 결과 없음

```
⚠️ 실시간 X 검색을 위해서는 Playwright MCP 연동이 필요합니다.
```

**해결:**
1. Claude에게 X 검색 요청: `"X에서 'lang:ko min_retweets:1000' 검색해줘"`
2. 결과를 JSON으로 저장
3. `--input` 옵션으로 전달

### 영상 생성 실패

```
❌ agentic_video.py not found
```

**해결:** `scripts/youtube-shorts/agentic_video.py` 파일 존재 확인

### JSON 파싱 오류

**해결:** 입력 JSON 형식 확인
```bash
python3 -m json.tool tweets.json
```

---

## 관련 문서

- [YouTube Shorts 스킬](../youtube-shorts/README.md)
- [X 스킬](../../.claude/skills/x/SKILL.md)
- [agentic_video.py](../youtube-shorts/agentic_video.py)

---

## 라이선스

이 프로젝트는 Michael AI Assistant의 일부입니다.

## 기여

버그 리포트나 기능 제안은 이슈를 통해 제출해주세요.
