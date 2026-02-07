---
name: ai-art-channel
description: |
  AI 아트 리액션 YouTube Shorts 생성기.
  X 트렌딩 AI 아트 수집 → 바이럴 분석 → 이미지 기반 쇼츠 생성.
  다음 키워드에 사용: "AI 아트 쇼츠", "AI 그림 영상", "미드저니 쇼츠", "AI 아트 채널"
allowed-tools: Bash(python3:*), Read, Write, Skill(x), Skill(youtube-shorts)
---

# AI 아트 리액션 채널 (YouTube Shorts)

X(Twitter)에서 바이럴되는 AI 아트 콘텐츠를 수집하고, 리액션 형식의 YouTube Shorts로 변환합니다.

## 채널 컨셉

**채널명**: 실화냐 AI

**콘텐츠 포맷** (60초):
```
[0-3초]   훅: "AI가 그린 고양이인데... 실화냐?"
[3-15초]  원본 AI 아트 공개 (Ken Burns 효과)
[15-35초] 리액션 + AI 도구/스타일 설명
[35-50초] 비교/추가 이미지
[50-60초] CTA + 해시태그
```

## 파이프라인 개요

```
X AI 아트 수집 → AI 도구/스타일 감지 → 바이럴 분석 → 쇼츠 생성
       ↓              ↓                    ↓              ↓
  Playwright     midjourney/sd/        감정/참여도     FFmpeg
                 dalle 감지           점수 산정      Ken Burns
```

## 사용 방법

### 1. 테스트 실행

```bash
# AI 아트 수집기 테스트
python3 scripts/ai-art-channel/art_collector.py --test

# 이미지 영상 변환 테스트
python3 scripts/ai-art-channel/image_video_maker.py --test

# 전체 파이프라인 테스트
python3 scripts/ai-art-channel/generate_ai_art_shorts.py --test
```

### 2. JSON 파일에서 분석

```bash
python3 scripts/ai-art-channel/generate_ai_art_shorts.py \
  --input tweets.json \
  --verbose
```

### 3. 자동 영상 생성

```bash
python3 scripts/ai-art-channel/generate_ai_art_shorts.py \
  --input tweets.json \
  --auto-generate \
  --video-mode image_only  # 비용 $0
```

### 4. 드라이런 (분석만)

```bash
python3 scripts/ai-art-channel/generate_ai_art_shorts.py \
  --query "midjourney min_faves:1000" \
  --dry-run
```

## AI 도구 감지

자동으로 다음 AI 도구를 감지합니다:

| 도구 | 키워드 |
|------|--------|
| Midjourney | midjourney, 미드저니, mj, --v5, --v6 |
| Stable Diffusion | stable diffusion, sd, 스테이블, sdxl |
| DALL-E | dall-e, dalle, 달리 |
| Flux | flux, 플럭스, flux.1 |
| Firefly | firefly, 파이어플라이, adobe |
| Leonardo | leonardo, 레오나르도 |

## 아트 스타일 감지

| 스타일 | 키워드 |
|--------|--------|
| 포토리얼 | realistic, photorealistic, 사실적 |
| 애니메이션 | anime, 애니, ghibli, 지브리 |
| 판타지 | fantasy, 판타지, magical, dragon |
| 사이버펑크 | cyberpunk, neon, futuristic |
| 초상화 | portrait, 초상화, face |
| 풍경 | landscape, 풍경, scenery |

## 추천 X 검색 쿼리

```
# 고참여도
midjourney min_faves:1000 filter:images
AI art min_retweets:500 filter:images

# 한국어
미드저니 min_faves:500 filter:images lang:ko
AI 그림 min_faves:300 filter:images lang:ko

# 감정 기반 (바이럴 잠재력 높음)
(실화 OR 대박 OR 미쳤) AI filter:images lang:ko

# 특정 주제
AI 고양이 filter:images min_faves:200 lang:ko
AI portrait min_faves:500 filter:images
```

## 비용 최적화

| 모드 | 방식 | 비용 | 품질 |
|------|------|------|------|
| **image_only** | FFmpeg Ken Burns | $0 | Good |
| hybrid | 이미지 + 부분 Veo | ~$1.50 | Great |
| full_veo | Veo 3.1 전체 | ~$3.00 | Premium |

**권장**: 대부분의 경우 `image_only` 모드로 충분합니다.

```bash
# 비용 $0 모드
python3 scripts/ai-art-channel/generate_ai_art_shorts.py \
  --input tweets.json \
  --auto-generate \
  --video-mode image_only
```

## Ken Burns 효과

이미지 기반 영상에 적용되는 효과:

| 효과 | 설명 |
|------|------|
| zoom_in_slow | 천천히 줌인 (드라마틱 공개) |
| zoom_out_slow | 천천히 줌아웃 (전체 공개) |
| pan_left_to_right | 왼쪽→오른쪽 패닝 |
| pan_right_to_left | 오른쪽→왼쪽 패닝 |
| diagonal_zoom | 대각선 줌 (역동적) |

## 바이럴 임계값

| 등급 | 점수 | 최소 좋아요 | 액션 |
|------|------|------------|------|
| must_publish | 90+ | 10,000+ | 무조건 발행 |
| high_priority | 80+ | 5,000+ | 고우선순위 |
| recommended | 70+ | 2,000+ | 추천 |
| consider | 60+ | 1,000+ | 고려 |

## Telegram 사용 예시

### 아이디어 수집

```
User: "AI 아트 쇼츠 만들어줘"

Michael:
🎨 AI 아트 트렌딩 수집 중...
📊 바이럴 AI 아트 5개 발견

1. [92점] 🎭 MIDJOURNEY - 포토리얼 고양이
   훅: "AI가 그린 고양이인데... 실화냐?"
   ❤️ 25,000 🔄 8,000

2. [88점] 🎯 STABLE DIFFUSION - 지브리 풍경
   훅: "스테이블 디퓨전으로 지브리 만들면..."
   ❤️ 18,000 🔄 5,000

3. [85점] 🎪 DALLE - 사이버펑크 도시
   훅: "달리로 만든 사이버펑크 실화냐?"
   ❤️ 12,000 🔄 3,500

🎬 어떤 걸로 영상 만들까요? (번호 선택)
```

### 영상 생성

```
User: "1번으로 쇼츠 만들어줘"

Michael:
🎬 '포토리얼 고양이' 쇼츠 제작 시작

[1/4] 🖼️ 이미지 처리 중...
[2/4] 🎬 Ken Burns 효과 적용 중...
[3/4] 🔤 텍스트 오버레이 적용 중...
[4/4] 📦 최종 영상 생성 중...

✅ 완료! 60초 영상
📍 파일: /tmp/ai-art-channel/ai_art_1234567.mp4
💰 비용: $0.00 (FFmpeg only)

📤 YouTube 업로드할까요?
```

## 출력 포맷

분석 결과는 JSON으로 저장됩니다:

```json
{
  "art_data": {
    "tweet_id": "...",
    "text": "미드저니로 만든 고양이...",
    "ai_tool": "midjourney",
    "art_style": "photorealistic",
    "art_confidence": 0.92,
    "media_urls": ["https://..."]
  },
  "analysis": {
    "viral_score": 87,
    "hook_suggestion": "AI가 그린 고양이인데... 실화냐?",
    "recommendation": "추천"
  }
}
```

## 파일 구조

```
.claude/skills/ai-art-channel/
└── SKILL.md                    # 이 파일

scripts/ai-art-channel/
├── config.py                   # 채널 설정
├── art_collector.py            # AI 아트 수집기
├── image_video_maker.py        # 이미지→영상 변환
└── generate_ai_art_shorts.py   # 메인 파이프라인
```

## 의존성

- `ffmpeg` - 영상 처리
- `ffprobe` - 영상 정보 추출
- 기존 `scripts/x-to-shorts/` 모듈 재사용:
  - `viral_analyzer.py` - 바이럴 분석
  - `text_overlay.py` - 텍스트 오버레이

## 수익화 로드맵

| 기간 | 목표 | 전략 |
|------|------|------|
| 0-3개월 | 구독자 1,000 | 일 3개 업로드 |
| 3-6개월 | 구독자 10,000 | 트렌드 최적화 |
| 6-12개월 | 구독자 100,000 | 브랜드 협찬 |

$ARGUMENTS
