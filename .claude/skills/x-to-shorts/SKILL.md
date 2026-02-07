---
name: x-to-shorts
description: |
  X(Twitter) 트렌드 기반 쇼츠 아이디어 생성기.
  트렌딩 트윗 → 바이럴 분석 → 쇼츠 콘셉트 변환.
  다음 키워드에 사용: "트렌드 쇼츠", "바이럴 아이디어", "X 쇼츠", "트위터 쇼츠", "트렌딩 영상"
allowed-tools: Bash(python3:*), Read, Write, Skill(x), Skill(youtube-shorts)
---

# X(Twitter) 트렌드 기반 Shorts 아이디어 생성기

X(Twitter)에서 바이럴/트렌딩 트윗을 수집하고 분석하여 YouTube Shorts 콘텐츠 아이디어를 자동 생성합니다.

## 파이프라인 개요

```
X 트렌딩 수집 → 바이럴 분석 → 아이디어 변환 → (선택) 영상 생성
     ↓              ↓              ↓              ↓
Playwright     감정/주제 분석   쇼츠 컨셉화    agentic_video.py
```

## 사용 방법

### 1. 아이디어만 생성
```bash
python3 scripts/x-to-shorts/generate_from_x.py \
  --query "lang:ko min_retweets:1000" \
  --count 5
```

### 2. 바로 영상까지 생성 (Veo)
```bash
python3 scripts/x-to-shorts/generate_from_x.py \
  --query "lang:ko min_retweets:1000" \
  --count 5 \
  --auto-generate
```

### 3. Sora로 영상 생성 (저렴한 옵션)
```bash
python3 scripts/x-to-shorts/generate_from_x.py \
  --query "lang:ko min_retweets:1000" \
  --count 5 \
  --auto-generate \
  --provider sora
```

### 3. 드라이런 (분석만)
```bash
python3 scripts/x-to-shorts/generate_from_x.py \
  --query "lang:ko min_retweets:500" \
  --dry-run
```

## X 스킬 연동

이 스킬은 기존 X 스킬(Playwright 기반)을 활용하여 트윗을 수집합니다.

### 추천 검색 쿼리

| 목적 | 쿼리 |
|------|------|
| 한국어 바이럴 | `lang:ko min_retweets:1000 -filter:replies` |
| 특정 주제 | `#AI min_faves:500` |
| 유머/밈 | `lang:ko min_retweets:2000 (짤 OR 웃긴 OR ㅋㅋ)` |
| 정보/팁 | `lang:ko (꿀팁 OR 팁) min_faves:1000` |
| 감성 콘텐츠 | `lang:ko (힐링 OR 감성 OR 분위기) filter:images` |

### 검색 연산자

| 연산자 | 설명 | 예시 |
|--------|------|------|
| `min_retweets:` | 최소 리트윗 수 | `min_retweets:1000` |
| `min_faves:` | 최소 좋아요 수 | `min_faves:5000` |
| `lang:` | 언어 필터 | `lang:ko` |
| `-filter:replies` | 답글 제외 | |
| `filter:images` | 이미지 포함 | |
| `filter:videos` | 비디오 포함 | |

## 바이럴 분석 기준

| 요소 | 가중치 | 설명 |
|------|--------|------|
| 참여율 | 30% | (RT + Like + Reply) / 기준치 |
| 감정 강도 | 25% | 긍정/부정/놀라움 지수 |
| 밈 잠재력 | 20% | 반복 가능한 포맷인가 |
| 시각 요소 | 15% | 이미지/영상 포함 여부 |
| 시의성 | 10% | 현재 트렌드와 연관성 |

## 아이디어 변환 유형

### 1. 반응형 (Reaction)
- 특징: "이거 실화냐" 류의 반응형 콘텐츠
- 훅: 충격적인 사실 공개
- 구조: 문제제시 → 반응 → 해설

### 2. 정보형 (Tutorial)
- 특징: "꿀팁" 류의 정보형 콘텐츠
- 훅: 이거 모르면 손해
- 구조: 문제 → 해결책 → 결과

### 3. 스토리형 (Story)
- 특징: 스토리텔링 기반 콘텐츠
- 훅: 어제 있었던 일
- 구조: 상황 → 전개 → 반전

### 4. 감성형 (Aesthetic)
- 특징: 감성/비주얼 중심 콘텐츠
- 훅: 분위기 있는 영상
- 구조: 장면1 → 장면2 → 마무리

## 출력 포맷

아이디어는 `project_plan.json` 호환 형식으로 출력됩니다:

```json
{
  "source_tweet": "원본 트윗 ID/링크",
  "brief": "아이디어 요약",
  "viral_score": 87,
  "template_type": "reaction",
  "continuity": { ... },
  "beat_sheet": { ... },
  "shots": [ ... ]
}
```

## Telegram 사용 예시

### 아이디어만 생성
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

...

🎬 영상으로 만들까요? (번호 선택)
```

### 선택 후 영상 생성
```
User: "2번으로 쇼츠 만들어줘"

Michael:
🎬 '일상 속 로봇 목격담' 쇼츠 제작 시작

1. Beat Sheet 생성 중...
2. Shot List 구성 중... (5 shots)
3. Veo 3.1 영상 생성 중...
4. FFmpeg 합성 중...

✅ 완료! 총 40초 영상
📤 YouTube 업로드할까요?
```

## 파일 구조

```
.claude/skills/x-to-shorts/
├── SKILL.md                    # 이 파일

scripts/x-to-shorts/
├── viral_analyzer.py           # 바이럴 분석 엔진
├── idea_transformer.py         # 아이디어 변환기
├── generate_from_x.py          # 메인 파이프라인
└── templates/
    ├── reaction.json           # 반응형 템플릿
    ├── tutorial.json           # 정보형 템플릿
    ├── story.json              # 스토리형 템플릿
    └── aesthetic.json          # 감성형 템플릿
```

## 프로바이더별 비용

| Provider | 클립당 비용 | 8클립 영상 | 특징 |
|----------|------------|-----------|------|
| **Sora** | $0.08~$0.32 | **~$2.50** | 저렴, 빠름 |
| Veo Fast | $1.20 | ~$10 | 중간 |
| Veo Standard | $3.20 | ~$26 | 고품질 |

**권장**: 대량 생성 시 `--provider sora` 사용

## 제약 사항

1. **X API 미사용**: Playwright 기반 브라우저 자동화 (기존 X 스킬 활용)
2. **저작권 주의**: 원본 트윗 크레딧 표시 권장
3. **비용**: 프로바이더에 따라 상이 (Sora 권장)

## 검증 방법

```bash
# 분석기 단독 테스트
python3 scripts/x-to-shorts/viral_analyzer.py --test

# 전체 파이프라인 테스트
python3 scripts/x-to-shorts/generate_from_x.py \
  --query "lang:ko min_retweets:500" \
  --dry-run
```

$ARGUMENTS
