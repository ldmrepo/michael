---
name: youtube-shorts
description: |
  YouTube Shorts 자동 생성 및 업로드 스킬.
  주제 입력 → 스크립트 생성 → Veo 영상 생성 → TTS 음성 합성 → YouTube 업로드
  다음 키워드에 사용: "유튜브", "youtube", "shorts", "쇼츠", "영상", "video", "숏폼"
allowed-tools: Bash(python3:*), Bash(curl:*), Read, Write
---

# YouTube Shorts 자동화 스킬 (2026 트렌드 최적화)

YouTube Shorts 영상을 자동으로 생성하고 업로드합니다.

## 파이프라인 개요

```
주제 입력 → 스크립트 생성 (Claude) → 영상+오디오 생성 (Veo 3.1) → 업로드 (YouTube)
```

**참고**: Veo 3.1은 네이티브 오디오 생성을 지원하여 별도 TTS가 필요 없습니다.

## 프롬프트 템플릿

템플릿 파일: `scripts/youtube-shorts/templates/prompts.json`

---

## 📊 2026 알고리즘 최적화 가이드

### 핵심 수치
| 지표 | 최적값 |
|------|--------|
| 영상 길이 | **50-60초** (76% 완주율) |
| 첫 3초 유지율 | **70% 이상** 목표 |
| 업로드 빈도 | **주 3-7회** |
| 시각 변화 주기 | **3-5초마다** |

### 알고리즘 신호
- ✅ 높은 완주율 (가장 중요)
- ✅ 반복 시청
- ✅ 좋아요/댓글/공유
- ❌ 빠른 스와이프 이탈

---

## 🎯 첫 3초 훅(Hook) 전략

**70%의 이탈이 첫 3초에 발생** - 훅이 가장 중요!

### 훅 유형별 템플릿

| 유형 | 예시 | 시각적 표현 |
|------|------|-------------|
| **질문형** | "이거 알고 계셨나요?" | 호기심 자극 클로즈업, 카메라 푸시인 |
| **충격형** | "99%가 모르는 사실" | 고대비 드라마틱 샷, 빠른 줌 |
| **직접 호출** | "지금 멈추세요" | 눈 마주침, 손짓, 4th wall break |
| **패턴 파괴** | 문장 중간에 시작 | 예상 못한 앵글, 색상 대비 |
| **변화 보여주기** | "이 변화를 보세요" | Before/After 스플릿, 만족스러운 전환 |

### 필수 체크리스트
- [ ] 시각적으로 강렬한 첫 프레임
- [ ] 얼굴 노출 (참여율 42% 증가)
- [ ] 음성 0.3초 내 시작
- [ ] 느린 도입부 없음 (바로 핵심으로)
- [ ] 가치 약속이 즉각적

---

## 🎬 Veo 3.1 프롬프트 공식

### 기본 구조
```
Subject + Action + Scene + Camera Movement + Lighting + Style + Audio
```

### 8-Point 스캐폴드
1. **Subject** (주체): 누가/무엇이
2. **Emotion** (감정): 어떤 분위기로
3. **Optics** (촬영): 샷 타입, 렌즈
4. **Motion** (움직임): 카메라 무브먼트
5. **Lighting** (조명): 조명 분위기
6. **Style** (스타일): 색감, 그레이딩
7. **Audio** (오디오): 음악, 효과음, 대사
8. **Continuity** (연속성): 씬 연결

### 카메라 무브먼트 옵션
```
동적: slow pan, tracking shot, dolly zoom, crane shot, steadicam follow
정적: locked off, tripod shot, fixed frame
창의적: dutch angle, POV shot, overhead shot, low angle hero shot, aerial view
전환: whip pan, match cut, morph transition, seamless zoom
```

### 조명 분위기
```
따뜻함: golden hour sunlight, warm candlelight, sunset orange glow
차가움: blue hour twilight, moonlit scene, cool fluorescent
드라마틱: dramatic rim lighting, high contrast chiaroscuro, silhouette backlit
자연스러움: soft natural daylight, dappled forest light
```

---

## 📝 장르별 프리셋

### 테크 리뷰
```
Lighting: clean studio lighting, subtle rim light
Camera: smooth product shots, macro details, rotating display
Style: modern minimal, tech aesthetic, blue accent colors
Audio: electronic ambient, clear voiceover
```

### 음식/레시피
```
Lighting: warm natural light, soft shadows
Camera: overhead shots, close-up textures, steam rising
Style: cozy warm tones, rustic elements, appetizing colors
Audio: cooking ASMR sounds, light acoustic music
```

### 피트니스
```
Lighting: dramatic gym lighting, high energy
Camera: dynamic tracking, slow-mo impacts, multiple angles
Style: high contrast, energetic, motivational
Audio: pump-up beats, breathing sounds, impact effects
```

### 여행
```
Lighting: golden hour, natural landscapes
Camera: drone shots, gimbal walks, epic reveals
Style: cinematic color grade, wanderlust aesthetic
Audio: inspiring orchestral or indie folk
```

### 힐링/자연
```
Lighting: natural ambient, weather-appropriate
Camera: slow cinematic pans, time-lapses, macro nature
Style: earth tones, peaceful, meditative
Audio: natural ambience, gentle instrumental
```

---

## 🎵 오디오 가이드라인

### 대화 규칙 (Veo 3.1)
- 대화는 **8초 이내**로 유지
- 자막 방지: `Character says: dialogue here` (따옴표 대신 콜론)
- 또는 `(no subtitles)` 추가
- 립싱크는 짧고 명확한 문장에 최적화

### 음악 싱크
- 트렌딩 사운드 첫 5초 사용 → **도달 21% 증가**
- 비트 드롭 = 시각적 전환과 일치
- 음악 에너지 = 콘텐츠 에너지 곡선 매치

### 사운드 디자인
- 액션에 만족스러운 효과음 (ASMR 스타일)
- 앰비언트 사운드로 몰입감 증가
- 드라마틱 순간에 침묵도 효과적

---

## 🎯 씬 구조 템플릿

### 교육 콘텐츠
```
Scene 1 (0-3s): {hook_visual}, close-up with dramatic lighting, immediate visual interest.
Scene 2 (3-10s): Wide shot establishing {problem_context}, slight camera movement, {mood} atmosphere.
Scene 3 (10-25s): Medium shot demonstrating {step_1}, smooth tracking shot, clear focus on action.
Scene 4 (25-40s): Close-up on {key_detail}, {camera_movement}, highlighting important element.
Scene 5 (40-55s): Reveal shot of {result}, pull-back to show full context, satisfying payoff.
Scene 6 (55-60s): Direct address or text overlay for CTA, warm inviting lighting.

Style: {visual_style}, 9:16 vertical, 4K quality
Audio: {audio_description}, clear narration, subtle background music
```

### 스토리텔링
```
Scene 1 (0-3s): {opening_shot}, cinematic framing, {hook_element} to grab attention.
Scene 2 (3-15s): Establishing shot of {setting}, slow camera movement, {time_of_day} lighting.
Scene 3 (15-25s): Medium shot of {character_action}, building tension, {mood} atmosphere.
Scene 4 (25-35s): Close-up reaction shot, emotional lighting, dramatic pause.
Scene 5 (35-50s): Wide shot {resolution_scene}, camera pulls back, triumphant music swell.
Scene 6 (50-60s): Final shot with {ending_visual}, fade or creative transition.

Style: cinematic, film-like quality
Audio: Emotional score, natural ambient, dialogue: "{short_dialogue}"
```

### 미적 바이브 (무나레이션)
```
Scene 1 (0-8s): {opening_visual}, slow motion, {lighting_mood}, dreamy atmosphere.
Scene 2 (8-20s): {second_visual}, smooth dolly or crane shot, {color_palette} tones.
Scene 3 (20-35s): {third_visual}, creative camera angle, seamless transition.
Scene 4 (35-50s): {fourth_visual}, dynamic movement, peak visual moment.
Scene 5 (50-60s): {closing_visual}, gentle fade or loop-friendly ending.

Style: highly polished, Instagram-worthy, ASMR-visual quality
Audio: {music_genre} beat, perfectly synced to visuals, no dialogue
```

---

## 📋 예시 프롬프트

### 석양 릴렉스
```
Scene 1 (0-3s): Breathtaking close-up of sun touching ocean horizon, golden hour light reflecting on gentle waves, slow camera tilt up.
Scene 2 (3-15s): Wide cinematic shot of beach silhouette, palm trees swaying, warm orange and purple sky, smooth dolly right.
Scene 3 (15-30s): Medium shot of waves washing over sand, foam patterns, golden backlight, relaxing rhythm.
Scene 4 (30-45s): Close-up of seashells and sand details, soft focus background, intimate perspective.
Scene 5 (45-60s): Final wide shot as sun dips below horizon, stars beginning to appear, gentle fade.

Style: Cinematic film look, warm color grading, 9:16 vertical, dreamy soft focus
Audio: Gentle ocean waves, distant seagulls, soft ambient piano melody
```

### 모닝 커피
```
Scene 1 (0-3s): Extreme close-up of coffee being poured, steam rising dramatically, rich brown colors, macro lens.
Scene 2 (3-12s): Pull back to reveal cozy morning scene, soft window light, warm bokeh background.
Scene 3 (12-25s): Overhead shot of hands wrapping around cup, cream swirling, satisfying spiral pattern.
Scene 4 (25-40s): Medium shot of peaceful moment, steam wisps catching light.
Scene 5 (40-55s): Close-up of first sip, content expression, warm feeling.
Scene 6 (55-60s): Wide shot of complete scene, loop-friendly ending.

Style: Warm cozy aesthetic, soft natural lighting, hygge vibes, film grain
Audio: Coffee pouring ASMR, gentle morning ambience, soft lo-fi beat
```

### 우주 탐험
```
Scene 1 (0-3s): Dramatic reveal of Earth from space, sun cresting horizon, lens flare, epic scale.
Scene 2 (3-15s): Sweeping camera past space station, stars background, Earth reflection on solar panels.
Scene 3 (15-30s): Close-up of astronaut helmet visor, Earth reflection visible, human element.
Scene 4 (30-45s): Pull back showing astronaut floating, nebula colors in distance, sense of wonder.
Scene 5 (45-60s): Final wide shot of galaxy, zoom into stars, infinite possibility.

Style: Cinematic sci-fi, deep blacks, vibrant nebula colors, epic scale, 4K
Audio: Hans Zimmer style orchestral, deep bass, ethereal choir
```

---

## ⚠️ 주의사항 (YouTube 2025.7 정책)

YouTube가 **저품질 AI 콘텐츠** 단속 강화:

| ❌ 피해야 할 것 | ✅ 해야 할 것 |
|----------------|--------------|
| 재사용/복사 콘텐츠 | 원본 분석/해설 추가 |
| 대량 생산 템플릿 영상 | 각 영상에 독창성 부여 |
| 반복적 AI 스팸 | 교육/오락/영감 주는 콘텐츠 |

**위반 시**: 전체 광고 수익 제거 가능

---

## 💻 스크립트 사용법

### 영상 생성 (Veo 3.1)
```bash
python3 scripts/youtube-shorts/generate-video.py \
  --prompt "프롬프트 내용" \
  --output /tmp/shorts/video.mp4
```

### YouTube 업로드
```bash
python3 scripts/youtube-shorts/upload-youtube.py \
  --video /tmp/shorts/video.mp4 \
  --title "영상 제목" \
  --description "영상 설명" \
  --tags "tag1,tag2,tag3"
```

### TTS 추가 (선택, Veo 3.1은 네이티브 오디오 포함)
```bash
python3 scripts/youtube-shorts/add-audio.py \
  --video /tmp/shorts/video.mp4 \
  --output /tmp/shorts/video-final.mp4 \
  --script "나레이션 텍스트"
```

---

## 🤖 Agentic Workflow (긴 영상 자동 생성)

**2026 최신 트렌드**: AI 에이전트가 전체 워크플로우를 오케스트레이션

### 파이프라인 구조
```
Creative Brief → Beat Sheet → Shot List → Continuity Table → Prompt Chain → Final Video
```

### 사용법

#### 기본 사용
```bash
python3 scripts/youtube-shorts/agentic_video.py \
  --brief "60초 커피 모닝 루틴 쇼츠"
```

#### 전체 옵션
```bash
python3 scripts/youtube-shorts/agentic_video.py \
  --brief "우주 여행 영상" \
  --style cinematic \
  --transition fade \
  --max-clips 8 \
  --output /tmp/shorts
```

#### 드라이런 (플랜만 생성)
```bash
python3 scripts/youtube-shorts/agentic_video.py \
  --brief "테스트 영상" \
  --dry-run
```

### 옵션 설명

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--brief` | (필수) | 영상 설명 |
| `--style` | cinematic | cinematic, vibrant, minimal, retro, dark |
| `--transition` | fade | fade, dissolve, wipeleft, wiperight, none |
| `--max-clips` | 8 | 최대 클립 수 (8클립 × 8초 = 64초) |
| `--output` | /tmp/shorts | 출력 디렉토리 |
| `--dry-run` | false | 플랜만 생성, 영상 미생성 |

### 8-Point Shot Grammar

각 샷은 8가지 요소로 정의:

| 요소 | 설명 | 예시 |
|------|------|------|
| subject | 피사체 | "steaming coffee cup" |
| emotion | 분위기 | "cozy, peaceful" |
| optics | 샷 타입 | "macro close-up" |
| motion | 카메라 | "slow dolly in" |
| lighting | 조명 | "golden hour" |
| style | 스타일 | "film grain" |
| audio | 사운드 | "soft acoustic" |
| continuity | 연속성 | "continues from previous" |

### 출력 파일

```
/tmp/shorts/
├── project_plan.json    # 전체 플랜 (Beat Sheet, Shot List)
├── clip_01.mp4          # 개별 클립들
├── clip_02.mp4
├── ...
├── frame_01.jpg         # 연속성용 프레임
└── final_1234567890.mp4 # 최종 영상
```

---

## 프로바이더 선택

| 프로바이더 | 비용 | 품질 | 속도 | 비고 |
|-----------|------|------|------|------|
| **veo** (기본) | ~$2.40/clip | 최고 | ~2분 | Veo 3.1 네이티브 오디오 |
| **sora** | ~$2/clip | 높음 | ~3분 | OpenAI API 키 필요 |
| **comfyui** | ~$0.10-0.25/clip | 좋음 | ~3-5분 | Vast.ai GPU, 비용 최적 |

환경변수로 기본 프로바이더 설정:
```bash
VIDEO_PROVIDER=comfyui    # comfyui 사용
COMFYUI_MODEL=wan22-i2v-a14b  # 고품질 14B 모델 (기본값)
# COMFYUI_MODEL=wan22-ti2v-5b  # 저비용 5B 모델
CUT_IMAGE_PROVIDER=gemini     # 컷 이미지: gemini (Imagen 4 Fast) 또는 flux (FLUX.2 Klein 4B)
VAST_API_KEY=xxx              # Vast.ai API 키 (ComfyUI 필수)
GOOGLE_API_KEY=xxx            # Imagen 4 Fast 사용 시 필수
```

### ComfyUI 사용법
```bash
# 단일 클립
python3 scripts/youtube-shorts/generate-video.py \
  --prompt "sunset over ocean" --provider comfyui -d 5

# 전체 파이프라인
python3 scripts/youtube-shorts/agentic_video.py \
  --brief "석양 릴렉스 영상" --provider comfyui
```

---

## 💰 비용 추정

| 항목 | 단가 | 클립당 |
|------|------|--------|
| Veo 3.1 Standard | $0.40/초 | ~$2.40 (6초) |
| Veo 3.1 Fast | $0.15/초 | ~$0.90 (6초) |
| ComfyUI 14B + Gemini | GPU+API | ~$0.18 (6초) |
| ComfyUI 5B + FLUX | GPU only | ~$0.065 (6초) |

**환경변수로 모델 선택**:
- `VEO_MODEL=veo-3.1-generate-preview` (Standard, 기본값)
- `VEO_MODEL=veo-3.1-fast-generate-preview` (Fast, 저렴)

---

## 🎯 예시 대화

```
User: "석양 쇼츠 만들어줘"

Michael:
1. 🎬 프롬프트 생성 중...
   [석양 릴렉스 템플릿 적용]

2. 🎥 Veo 3.1 영상 생성 중... (약 40초)
   ✅ 영상 생성 완료 (3.68 MB, 네이티브 오디오 포함)

3. 📤 YouTube 업로드 중...
   ✅ 업로드 완료!

📺 https://youtube.com/shorts/CL1RYv5tmwU
```
