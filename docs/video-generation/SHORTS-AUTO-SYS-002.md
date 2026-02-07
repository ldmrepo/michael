# AI 쇼츠 자동 생성 최종 시스템 설계 문서

| 항목 | 내용 |
|------|------|
| **문서 ID** | SHORTS-AUTO-SYS-002 |
| **버전** | v2.0.0 |
| **작성일** | 2026-02-07 (Asia/Seoul) |
| **이전 버전** | v1.0.0 (SHORTS-AUTO-SYS-001) |
| **목적** | 프론티어 LLM(스토리/연출) + 이미지 생성(컷 고정) + ComfyUI 영상 생성(I2V/VACE) + 후처리/배포 자동화를 통해 안정적·고품질·대량 생산 가능한 유튜브 쇼츠 생성 시스템 구축 |
| **대상** | ML/플랫폼 엔지니어, 백엔드 엔지니어, MLOps/Infra, 콘텐츠 운영자 |

---

## v2.0 주요 변경사항 (v1.0 대비)

| 영역 | v1.0 | v2.0 |
|------|------|------|
| 비디오 생성 모델 | Wan2.1 (일반 I2V) | **Wan2.2 MoE DiT** (A14B I2V + TI2V-5B) |
| 이미지 생성 | 나노바나나 (명세 미상) | **Nano Banana Pro** (Google Gemini 3 기반) + FLUX.2 fallback |
| VACE 파이프라인 | 미포함 | **Wan2.1/2.2 VACE** (R2V, V2V, Masked Editing) 추가 |
| FLF2V 워크플로우 | 미포함 | **First-Last Frame** 기반 샷 전환 품질 강화 추가 |
| 가속 기법 | 미포함 | **TeaCache (~30%), Lightning LoRA (~80%)** 추가 |
| 오디오 생성 | TTS 후처리만 언급 | TTS 명세 구체화 + **Seedance API (Joint Audio-Video)** 중장기 경로 |
| QC 기준 | 기본형 | **SSIM 프레임 일관성, 오디오-비디오 길이 검증** 추가 |
| 비용 추정 | 미포함 | **샷/쇼츠 단위 비용 baseline** 추가 |
| 샷 스키마 | 기본형 | **transition 필드** 추가 |

---

## 1. 배경과 핵심 결론

### 1.1 문제 정의

- 단일 T2V로 30~60초를 생성하면 장기 일관성 붕괴(캐릭터 드리프트, 조명/톤 변화, 모션 붕괴) 및 실패율/비용 증가가 발생한다.
- 유튜브 쇼츠는 리텐션/훅/리듬이 중요하고, "한 번에 길게"보다 "짧은 샷을 잘 연결"하는 편이 성과가 좋다.

### 1.2 최종 결론 (표준 방식)

```
스토리 생성 → 샷 분해(카메라/조명 포함) → 컷 이미지 고정(Nano Banana Pro)
→ I2V로 5~7초 샷 생성(ComfyUI + Wan2.2) → VACE 보강(선택)
→ 후처리(자막/TTS/BGM/인코딩) → 30~60초로 합성/배포
```

이 구조가 안정성·품질·재현성·비용·자동화에서 최적이다.

### 1.3 2026년 트렌드 반영 근거

- **Wan2.2 MoE DiT**: 2025.07 공개, ComfyUI/Diffusers 네이티브 통합 완료. High/Low Noise 2-pass 구조로 품질 향상.
- **VACE (Video All-in-One Creation and Editing)**: Reference-to-Video, Video-to-Video, Masked Editing을 단일 모델로 통합. 캐릭터 일관성 및 모션 제어 강화.
- **Nano Banana Pro**: Google Gemini 3 기반, 캐릭터 일관성/멀티씬 일관성에서 FLUX Kontext 대비 우위. ~3~5초/이미지 생성.
- **Joint Audio-Video 생성**: Seedance 1.5 Pro/2.0 등이 비디오+오디오 동시 생성 지원. 단, 클라우드 API 전용(설치형 불가).

---

## 2. 목표와 비목표

### 2.1 목표

- 30초/60초 고품질 쇼츠를 안정적으로 생성 (재현 가능)
- 샷 단위 재시도/부분 재생성 가능
- 대량 배치(예: 1k~10k/월)로 확장 가능
- 비용 최적화(Vast.ai 포함) 및 품질 기준(QC) 기반 자동 승인/거절

### 2.2 비목표 (초기 범위 제외)

- 완전 실시간(초저지연) 생성
- 사용자별 복잡한 상호작용 편집 UI
- 독자적인 비디오 생성 모델 학습 (파인튜닝/학습은 추후)
- Joint Audio-Video 네이티브 생성 (Phase 3 이후 검토)

---

## 3. 시스템 개요 아키텍처

### 3.1 논리 아키텍처 (권장)

```
┌─────────────────────────────────────────────────────────────┐
│                     Orchestrator                            │
│          (Queue / Worker / Retry / Metadata)                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ① Story Director ──→ ② Shot Planner ──→ ③ Cut Generator   │
│     (Frontier LLM)     (Shotization +      (Nano Banana     │
│                         Camera/Lighting)    Pro / FLUX.2)   │
│                                                   │         │
│                              ┌────────────────────┘         │
│                              ▼                              │
│                    ④ Video Renderer                          │
│                       (ComfyUI)                             │
│                    ┌──────┼──────┐                          │
│                    │      │      │                          │
│                  I2V    FLF2V  VACE                         │
│                (Wan2.2) (Wan2.2)(Wan2.1/2.2)                │
│                    │      │      │                          │
│                    └──────┼──────┘                          │
│                           ▼                                 │
│              ⑤ Post-Production ──→ ⑥ Publish & Analytics    │
│                 (FFmpeg/TTS/BGM)     (업로드/스케줄/성과)      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. 파이프라인 상세 설계

### 4.1 단계 A: 스토리 생성 (Frontier LLM)

**역할**
- 콘텐츠 목표(교육/정보/스토리/마케팅)에 맞는 내러티브 생성
- 전체 길이(30초/60초) 및 훅 구조 반영

**산출물 (필수)**
- 제목 / 주제 / 대상 / 톤
- 내레이션 스크립트 (문장 단위 타임라인 가능)

---

### 4.2 단계 B: 샷 분해 + 연출 스크립트

**핵심 원칙**
- 1 Shot = 5~7초
- Shot마다 카메라 무브 1개, 주체 1개 (가능한 단일 주제)
- 조명은 프리셋 기반(일관성)으로 제한된 vocabulary 사용
- **v2.0 추가**: 샷 간 `transition` 필드로 전환 방식 명시

**표준 Shot 스키마 (v2.0)**

```json
{
  "video_id": "uuid",
  "format": "shorts_9_16",
  "duration_sec": 60,
  "shots": [
    {
      "shot_id": 1,
      "duration_sec": 6,
      "visual_description": "...",
      "camera": {
        "type": "slow zoom in",
        "framing": "medium close-up",
        "angle": "eye level",
        "speed": "very slow"
      },
      "lighting": {
        "style": "soft cinematic",
        "key_light": "front-left",
        "contrast": "low",
        "color_temp": "warm"
      },
      "mood": "curiosity",
      "narration": "...",
      "on_screen_text": "...(optional)",
      "transition": {
        "type": "crossfade",
        "duration_ms": 500
      },
      "rendering_hint": "i2v"
    }
  ]
}
```

**transition.type 허용 값**
- `cut` (기본값, 즉시 전환)
- `crossfade` (페이드 오버랩)
- `fade_to_black`
- `fade_from_black`

**rendering_hint 허용 값**
- `i2v` (기본, 컷 이미지 → 영상)
- `flf2v` (인접 샷 연결부, First-Last Frame)
- `t2v` (B-roll, 보조 장면)
- `vace_r2v` (캐릭터 일관성 강화 필요 시)

**카메라 vocabulary (권장 최소 세트)**
- static shot, slow zoom in, slow zoom out, gentle pan left/right, tilt up/down, tracking shot
- (운영 안정성을 위해 세트 고정)

**조명 프리셋 (권장)**
- soft cinematic, single key light, consistent color temperature, low contrast, no harsh shadows

---

### 4.3 단계 C: 컷 이미지 생성

**목적**: 캐릭터/구도/스타일/조명 톤을 프레임 단위로 고정해 영상 모델을 "렌더러"로 사용

#### 모델 선택 기준

| 모델 | 용도 | 강점 | 비용 |
|------|------|------|------|
| **Nano Banana Pro** (기본) | 대부분의 컷 이미지 | 캐릭터 일관성, 멀티씬 일관성, 빠른 생성(~3~5초) | ~$0.02/이미지 |
| **FLUX.2 [max]** (고품질 fallback) | 특수 고해상도/정밀 스타일 | 4MP 초고해상도, 32B 파라미터, 정밀 라이팅 제어 | ~$0.03/이미지 |
| **Seedream 4.0/4.5** (스타일 특화) | 일러스트/특정 스타일 요구 시 | 스타일라이즈 강점 | ~$0.02/이미지 |

#### Nano Banana Pro 프롬프트 규칙 (핵심)

```
single subject, centered composition, vertical 9:16,
consistent character appearance, [캐릭터 상세 묘사],
[카메라 프레이밍], [조명 프리셋],
no motion blur, cinematic composition, high detail
```

**주의사항**:
- Nano Banana Pro는 Google Gemini 3 기반으로, 실세계 지식과 추론 능력을 활용한 컨텍스트 이해가 강점
- 멀티이미지 컨텍스트 지원: 동일 캐릭터의 이전 컷을 참조 이미지로 제공하면 일관성 향상
- API 접근: Vercel AI SDK, FAL.AI, flux-ai.io 등을 통해 호출 가능

**산출물**
- `cut_0001.png` … `cut_0010.png` (샷 수만큼)
- 각 이미지에 대응하는 `cut_meta.json` (prompt, seed, style preset, shot_id, model_used)

---

### 4.4 단계 D: 영상 생성 (ComfyUI)

#### 4.4.1 모델 구성 (v2.0 — Wan2.2 기준)

| 모델 | 파일 | 용도 | VRAM 요구 |
|------|------|------|-----------|
| **Wan2.2-I2V-A14B** (high noise) | `wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors` | I2V 1차 패스 (구조/레이아웃) | ~24GB |
| **Wan2.2-I2V-A14B** (low noise) | `wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors` | I2V 2차 패스 (디테일) | ~24GB |
| **Wan2.2-TI2V-5B** | `wan2.2_ti2v_5B_fp16.safetensors` | 대량 생산용 통합 T2V+I2V | ~8GB |
| **Wan2.1-VACE-14B** | `wan2.1_vace_14B_fp16.safetensors` | R2V/V2V/Masked Editing | ~24GB |
| **Text Encoder** | `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | 공통 텍스트 인코더 | — |
| **VAE** | `wan_2.1_vae.safetensors` (또는 `wan2.2_vae.safetensors`) | 공통 VAE | — |
| **CLIP Vision** | `clip_vision_h.safetensors` | I2V용 이미지 인코딩 | — |

**공통 모델 경로 (ComfyUI)**
```
ComfyUI/
├── models/
│   ├── diffusion_models/
│   │   ├── wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors
│   │   ├── wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors
│   │   ├── wan2.2_ti2v_5B_fp16.safetensors
│   │   └── wan2.1_vace_14B_fp16.safetensors
│   ├── text_encoders/
│   │   └── umt5_xxl_fp8_e4m3fn_scaled.safetensors
│   ├── vae/
│   │   └── wan_2.1_vae.safetensors
│   ├── clip_vision/
│   │   └── clip_vision_h.safetensors
│   └── loras/
│       ├── Wan2.2-Lightning_I2V-A14B-4steps-lora_HIGH_fp16.safetensors
│       └── Wan2.2-Lightning_I2V-A14B-4steps-lora_LOW_fp16.safetensors
```

#### 4.4.2 렌더링 전략

| 렌더링 모드 | 비율 | 모델 | 용도 |
|-------------|------|------|------|
| **I2V** (2-pass) | 70~80% | Wan2.2-I2V-A14B | 메인 샷 (컷 이미지 기반) |
| **FLF2V** | 10~15% | Wan2.2-I2V-A14B | 인접 샷 연결부 (시작/끝 프레임 고정) |
| **VACE R2V** | 5~10% | Wan2.1-VACE-14B | 캐릭터 일관성 보강이 필요한 샷 |
| **T2V** | 5~10% | Wan2.2-TI2V-5B | B-roll, 전환 장면 |

#### 4.4.3 I2V 2-Pass 워크플로우 (Wan2.2-A14B)

Wan2.2의 핵심 혁신은 **MoE (Mixture-of-Experts) 디퓨전 아키텍처**로, high-noise expert(초기 글로벌 레이아웃)와 low-noise expert(후기 디테일)를 분리하여 품질을 향상시킨다.

```
LoadImage → CLIPVisionEncode
                    ↓
LoadDiffusionModel(high_noise) → KSampler(1차 패스)
                    ↓
LoadDiffusionModel(low_noise)  → KSampler(2차 패스)
                    ↓
              VAEDecode → SaveVideo
```

#### 4.4.4 FLF2V (First-Last Frame) 워크플로우

**목적**: 인접 샷의 마지막 프레임과 다음 샷의 첫 프레임을 고정하여 전환 품질 강화

```
LoadImage(시작 프레임) + LoadImage(끝 프레임)
                    ↓
        WanFirstLastFrameToVideo
                    ↓
           KSampler → VAEDecode → SaveVideo
```

**적용 시점**: Shot 스키마의 `rendering_hint: "flf2v"` 또는 `transition.type: "crossfade"` 인 경우

#### 4.4.5 VACE 워크플로우

**목적**: 캐릭터 일관성 강화, 모션 전이, 스타일 전환, 부분 편집

| VACE 모드 | 입력 | 용도 |
|-----------|------|------|
| **R2V** (Reference-to-Video) | 참조 이미지 + 프롬프트 | 캐릭터 외형을 유지하면서 새로운 장면 생성 |
| **V2V** (Video-to-Video) | 소스 비디오 + 참조 이미지 | 포즈/깊이 기반 스타일 전환 |
| **MV2V** (Masked Video Editing) | 비디오 + 마스크 | 특정 영역 인페인팅/교체 |

```
LoadImage(참조) + WanVaceToVideo
                    ↓
       KSampler → TrimVideoLatent → VAEDecode → SaveVideo
```

**VACE 활용 시나리오**:
- 캐릭터가 여러 샷에 걸쳐 등장할 때, R2V로 일관성 보장
- I2V 결과에서 특정 부분만 수정이 필요할 때, MV2V로 부분 재생성
- 이전 샷의 모션을 다음 샷에 전이할 때, V2V + DepthAnything/DW Pose

#### 4.4.6 표준 생성 파라미터

| 파라미터 | 고품질 (A14B) | 대량생산 (TI2V-5B) | Lightning (A14B + LoRA) |
|----------|---------------|--------------------|-----------------------|
| Aspect | 9:16 | 9:16 | 9:16 |
| 해상도 | 720×1280 | 480×832 | 720×1280 |
| FPS | 24 | 24 | 24 |
| Frames | 121(~5s) / 145(~6s) / 169(~7s) | 121(~5s) | 121(~5s) / 145(~6s) |
| Steps | 28~32 | 28~32 | **4** |
| CFG | 6.5~7.5 | 6.5~7.5 | 6.5~7.5 |
| Split Step (2-pass) | 14~16 | — | 2 |
| Seed | 랜덤 (재현 시 고정) | 랜덤 | 랜덤 |

**가속 옵션 비교**

| 방식 | Steps | 속도 향상 | 품질 영향 | 용도 |
|------|-------|-----------|-----------|------|
| 기본 (A14B 2-pass) | 28~32 | 기준 | 최고 | 고품질 |
| TeaCache | 28~32 | ~30% 빠름 | 거의 동일 | 고품질 + 속도 |
| **Lightning LoRA** | **4** | **~80% 빠름** | 약간 하락 | 대량 생산 / 프리뷰 |

**운영 원칙**
- GPU 1장 = 동시 1 job (품질/안정성)
- 실패 시 해당 샷만 재시도 (전체 재생성 금지)
- A14B는 24GB VRAM 이상 필수, TI2V-5B는 8GB에서 동작

---

### 4.5 단계 E: 후처리 / 합성 (FFmpeg 중심)

#### 4.5.1 필수 체인

1. **프레임 보간** (옵션): 24→48fps (FILM 또는 RIFE 사용)
2. **컬러/톤 정리** (프리셋 기반)
3. **업스케일** (선택): 720p → 1080p
4. **자막**: ASS/SRT 기반, 스타일 표준화
5. **내레이션 (TTS)**: 아래 TTS 명세 참조
6. **BGM / SFX**: 볼륨 노멀라이즈, 페이드 인/아웃
7. **샷 합성**: `transition` 스키마 기반 전환 효과 적용
8. **최종 인코딩**: h264, yuv420p, -movflags faststart

#### 4.5.2 TTS 명세 (v2.0 신규)

| 항목 | 권장 |
|------|------|
| **엔진** | ElevenLabs API (고품질) / Edge-TTS (저비용 대량) |
| **화자 선택** | 콘텐츠 톤에 따라 프리셋 (교육: 차분/신뢰, 스토리: 감성/극적) |
| **언어** | 한국어 기본, 다국어 확장 시 화자별 프로필 |
| **타이밍 싱크** | 내레이션 오디오 길이 기준으로 샷 duration 역조정 |
| **출력 포맷** | WAV 48kHz 16bit → FFmpeg에서 최종 믹싱 |

**타이밍 동기화 전략**:
- Shot의 `narration` 텍스트로 TTS 생성 → 오디오 길이 측정
- 오디오 길이가 샷 duration 초과 시: narration 분할 또는 샷 duration 조정
- 자막 타임스탬프는 TTS 워드 타이밍에서 자동 추출

#### 4.5.3 전환 효과 (transition 기반)

```bash
# crossfade (500ms)
ffmpeg -i shot1.mp4 -i shot2.mp4 -filter_complex "xfade=transition=fade:duration=0.5:offset=5.5"

# fade_to_black → fade_from_black
ffmpeg -i shot.mp4 -vf "fade=t=out:st=5:d=0.5" ...
```

#### 4.5.4 최종 산출물

- `final_short_30s.mp4` / `final_short_60s.mp4`
- `final_meta.json` (샷 구성, 모델/워크플로우 해시, 비용, 런타임)

---

## 5. 오케스트레이션 / 운영 설계

### 5.1 구성요소

| 구성요소 | 기술 | 역할 |
|----------|------|------|
| **API Gateway** | FastAPI | Job 생성 요청, 상태 조회, 결과 URL 제공 |
| **Queue** | Redis | 작업 큐, 재시도 큐, 우선순위 큐 |
| **Story Worker** | LLM API | 스토리 생성 + 샷 분해 |
| **Cut Worker** | Nano Banana Pro / FLUX.2 API | 컷 이미지 생성 |
| **Video Worker** | ComfyUI (Wan2.2 / VACE) | 영상 렌더링 |
| **Post Worker** | FFmpeg + TTS API | 후처리 / 합성 |
| **Storage** | S3/GCS/MinIO | 영상/이미지/자막/오디오 |
| **DB** | PostgreSQL | Job/Shot 상태, 메타데이터, 비용/성과 로그 |
| **Metrics** | Prometheus + Grafana | GPU 사용률, 실패율, 클립당 비용, 처리량 |

### 5.2 상태 머신 (권장)

```
QUEUED
  → STORY_DONE
    → SHOTS_PLANNED
      → CUTS_DONE
        → RENDERING
          → POST_PROCESSING
            → COMPLETED

실패 시:
  → FAILED_RETRYABLE (자동 재시도, 최대 3회)
  → FAILED_FINAL (수동 검토 대기)
```

---

## 6. 품질 (QC) 및 자동 재시도 정책

### 6.1 실패 유형별 자동 조치

| 실패 유형 | 자동 조치 |
|-----------|-----------|
| **OOM** | 해상도↓ → frames↓ → steps↓ 순으로 자동 다운시프트 |
| **검은 화면/깨짐 (VAE)** | VAE 파일/노드 검증 후 재시도 |
| **모션 붕괴/드리프트** | CFG↓ / 카메라 단순화 / VACE R2V 전환 |
| **타임아웃** | 샷 분할(7s→5s) 또는 Lightning LoRA로 재시도 |
| **캐릭터 불일치** | VACE R2V로 재생성 (참조 이미지 강화) |

### 6.2 QC 자동 판정

#### Phase 1 (기본형)

| 지표 | 기준 | 자동 조치 |
|------|------|-----------|
| 해상도/프레임 누락 | 기대값 대비 ±5% | 재생성 |
| 파일 손상 | FFprobe 검증 실패 | 재생성 |
| 길이 불일치 | ±0.5초 이상 | 재생성 |
| 과도한 블랙 프레임 | >15% 비율 | 재생성 |
| **SSIM 프레임 일관성** (v2.0) | 인접 프레임 SSIM < 0.7 | 모션 붕괴 의심 → 재생성 |
| **오디오-비디오 길이 검증** (v2.0) | 차이 > 0.3초 | TTS 재생성 또는 트리밍 |

#### Phase 2+ (고도화)

- 멀티모달 모델로 "캐릭터 일관성/자막 가독성/훅 강도" 평가
- 유튜브 리텐션 데이터 피드백 루프

---

## 7. 비용 / 성능 최적화 전략

### 7.1 샷/쇼츠 단위 비용 추정 (v2.0 신규)

#### 단일 샷 (6초) 예상 비용

| 단계 | 고품질 (A14B) | 대량 (TI2V-5B) | Lightning |
|------|---------------|----------------|-----------|
| 컷 이미지 (Nano Banana Pro) | $0.02 | $0.02 | $0.02 |
| 영상 렌더링 (GPU 시간) | ~$0.15 (4090, ~3분) | ~$0.05 (4090, ~1분) | ~$0.04 (4090, ~40초) |
| TTS (ElevenLabs) | ~$0.01 | ~$0.005 (Edge-TTS 무료) | ~$0.005 |
| 후처리 (FFmpeg) | ~$0.01 | ~$0.01 | ~$0.01 |
| **소계** | **~$0.19** | **~$0.085** | **~$0.075** |

#### 쇼츠 1개 예상 비용

| 길이 | 고품질 | 대량 | Lightning |
|------|--------|------|-----------|
| 30초 (5샷) | ~$1.0 | ~$0.45 | ~$0.40 |
| 60초 (10샷) | ~$2.0 | ~$0.90 | ~$0.80 |

#### 월간 대량 생산 비용 추정

| 규모 | 고품질 60초 | 대량 60초 | 비고 |
|------|------------|----------|------|
| 100개/월 | ~$200 | ~$90 | 소규모 |
| 1,000개/월 | ~$2,000 | ~$900 | 중규모, Vast.ai 할인 적용 시 ~30% 절감 |
| 10,000개/월 | ~$20,000 | ~$9,000 | 대규모, 전용 GPU 풀 권장 |

> 참고: Vast.ai RTX 4090 시간당 ~$0.20~$0.40 기준. 실제 비용은 인스턴스 가용성/지역에 따라 변동.

### 7.2 생성 전략

- 생성은 720p 이하, 업스케일/보간은 후처리로
- 샷 단위 캐시 (컷 이미지/프롬프트/시드 저장)로 재생성 비용 절감
- 대량 생산 시 Lightning LoRA로 ~80% 속도 향상

### 7.3 Vast.ai 운영 (권장)

| 용도 | 인스턴스 | 모델 |
|------|----------|------|
| 대량 생산 | RTX 4090 (24GB) × N | Wan2.2-TI2V-5B 또는 Lightning |
| 고품질 | RTX 4090 (24GB) | Wan2.2-I2V-A14B 2-pass |
| VACE 보강 | RTX 4090 (24GB) | Wan2.1-VACE-14B |
| 긴급 / fallback | 상용 API (Seedance 등) | — |

**인스턴스 생명주기**:
- 작업 없으면 자동 stop (5분 idle timeout)
- 큐 길이에 따라 자동 scale-out/in

---

## 8. 보안 / 컴플라이언스 (필수 항목)

- **외부 LLM 사용 시**: 프롬프트/원문 데이터 민감도 정책, PII 제거/마스킹
- **저장소 접근**: Signed URL, 권한 최소화
- **워크플로우/모델 파일**: 해시/버전 고정 (재현성 + 공급망 리스크 최소화)
- **API 키 관리**: 환경변수 또는 시크릿 매니저, 코드에 하드코딩 금지

---

## 9. Michael (유튜브쇼츠생성기) 통합 설계

### 9.1 Provider Router (정책)

```
                        ┌─ 이미지 소스 있음 → FFmpeg (Ken Burns/모션)
                        │
Request ──→ Router ─────┼─ 기본값 → ComfyUI I2V (Wan2.2-A14B)
                        │
                        ├─ 대량 생산 → ComfyUI (Wan2.2-TI2V-5B + Lightning)
                        │
                        ├─ 캐릭터 일관성 필요 → ComfyUI VACE R2V
                        │
                        ├─ 고품질 + 오디오 필요 → Seedance API (클라우드)
                        │
                        └─ 긴급 fallback → 상용 API (Kling/Runway 등)
```

### 9.2 표준 인터페이스 (권장)

- `POST /jobs` — 주제/길이/스타일/언어/타겟
- `GET /jobs/{id}` — 상태 조회
- `GET /jobs/{id}/artifacts` — 결과 URL 목록
- `POST /jobs/{id}/shots/{shot_id}/retry` — 개별 샷 재시도
- `GET /jobs/{id}/cost` — 비용 내역

---

## 10. 템플릿 / 리소스 표준 (운영 핵심)

### 10.1 워크플로우 템플릿

| 파일 | 용도 | 모델 |
|------|------|------|
| `workflows/shorts_i2v_720p_wan22.json` | 고품질 I2V | Wan2.2-A14B 2-pass |
| `workflows/shorts_i2v_480p_wan22.json` | 대량 I2V | Wan2.2-TI2V-5B |
| `workflows/shorts_i2v_720p_lightning.json` | 고속 I2V (v2.0) | Wan2.2-A14B + Lightning LoRA |
| `workflows/shorts_flf2v_720p.json` | 샷 전환 (v2.0) | Wan2.2-A14B FLF2V |
| `workflows/shorts_vace_r2v.json` | 캐릭터 일관성 (v2.0) | Wan2.1-VACE-14B |
| `workflows/shorts_vace_v2v.json` | 모션 전이 (v2.0) | Wan2.1/2.2-VACE |
| `workflows/shorts_t2v_broll.json` | B-roll 보조 | Wan2.2-TI2V-5B |
| `workflows/post_subtitle_ass.json` | 자막 생성 | FFmpeg |
| `workflows/post_mix_audio.json` | BGM/TTS 믹싱 | FFmpeg |

### 10.2 저장 메타데이터 (반드시)

```json
{
  "story_prompt": "...",
  "story_output_hash": "sha256:...",
  "shots_json_hash": "sha256:...",
  "cuts": [
    {
      "shot_id": 1,
      "prompt": "...",
      "seed": 12345,
      "model": "nano-banana-pro",
      "model_revision": "2026-01"
    }
  ],
  "rendering": {
    "comfy_workflow_hash": "sha256:...",
    "model": "wan2.2-i2v-a14b",
    "params": {
      "steps": 30,
      "cfg": 7.0,
      "frames": 145,
      "fps": 24,
      "lightning_lora": false
    }
  },
  "runtime_sec": 180,
  "gpu": "RTX 4090",
  "cost_estimate_usd": 0.19,
  "qc_result": "passed",
  "qc_ssim_min": 0.82,
  "retry_count": 0
}
```

---

## 11. 권장 "베스트 구성" 요약

### 30초 고품질

- 6초 × 5 shots 또는 5초 × 6 shots
- 초반 2샷은 훅 강화 (zoom-in, 텍스트 온스크린)
- 인접 샷 1~2개에 FLF2V 적용으로 전환 품질 확보
- 모델: Wan2.2-I2V-A14B 2-pass

### 60초 고품질

- 5초 × 10~12 shots
- 중간에 1~2개 B-roll (T2V)로 리듬 유지
- 캐릭터 등장 샷은 VACE R2V로 일관성 강화
- 모델: Wan2.2-I2V-A14B + VACE 혼합

### 60초 대량 생산

- 5초 × 10~12 shots
- 모델: Wan2.2-TI2V-5B 또는 A14B + Lightning LoRA (4-step)
- QC 기본형 자동 통과/재생성
- 목표: 클립당 ~$0.80 이하

### 품질 안정 공식

```
연출 스크립트(카메라/조명)
  + 컷 이미지 고정 (Nano Banana Pro)
  + I2V 렌더링 (Wan2.2 2-pass)
  + VACE 보강 (캐릭터 일관성)
  + FLF2V (샷 전환부)
  + 후처리 표준화 (FFmpeg + TTS 싱크)
```

---

## 12. 단계별 구축 로드맵

### Phase 1 — POC (단일 GPU)

- [ ] Story → Shots → Cuts (Nano Banana Pro) → I2V (Wan2.2-A14B) → FFmpeg 합성
- [ ] 샷 단위 재시도 + 메타데이터 저장
- [ ] TTS 파이프라인 (ElevenLabs 또는 Edge-TTS)
- [ ] 기본 QC (해상도/길이/블랙프레임/SSIM)
- [ ] 비용 baseline 측정 및 검증

### Phase 2 — 하이브리드 / 대량

- [ ] Redis 큐 + 다중 Worker + Vast.ai 확장
- [ ] Lightning LoRA 대량생산 워크플로우 추가
- [ ] FLF2V 워크플로우 통합
- [ ] VACE R2V 캐릭터 일관성 파이프라인
- [ ] QC 자동화 (기본형) + 실패 자동 분류
- [ ] Provider Router 구현

### Phase 3 — 프로덕션

- [ ] SLA 기반 라우팅 (품질/비용/지연)
- [ ] 자동 업로드 / 스케줄링 / 성과 피드백 루프
- [ ] 품질 평가 고도화 (멀티모달 QC)
- [ ] Seedance API 통합 (Joint Audio-Video, 고품질 경로)
- [ ] EchoShot / LTXVideo 등 특수 모델 평가 및 선택적 도입

---

## 13. 최종 체크리스트

- [ ] Shot 스키마 (JSON) 표준 확정 — **v2.0: transition/rendering_hint 필드 포함**
- [ ] 카메라/조명 vocabulary/preset 확정
- [ ] Nano Banana Pro 컷 생성 프롬프트 템플릿 확정
- [ ] **Wan2.2 모델 파일 다운로드 및 경로 배치**
- [ ] ComfyUI I2V 워크플로우 템플릿 (480/720/Lightning) 확정
- [ ] **FLF2V 워크플로우 템플릿 확정**
- [ ] **VACE R2V 워크플로우 템플릿 확정**
- [ ] Queue/Worker/Retry 정책 확정
- [ ] **TTS 엔진 선정 및 타이밍 싱크 방식 확정**
- [ ] FFmpeg 인코딩/자막/전환효과 스타일 표준 확정
- [ ] 메타데이터 저장/재현성 (해시/버전 고정) 적용
- [ ] Vast.ai 인스턴스 자동 관리 (Stop/Scale) 적용
- [ ] **비용 baseline 측정 및 검증**
- [ ] **QC SSIM/오디오-비디오 길이 검증 구현**

---

## 부록 A: 모델 비교 요약

### 비디오 생성 모델 (오픈소스, 설치형)

| 모델 | 파라미터 | 아키텍처 | 해상도 | VRAM | ComfyUI | 용도 |
|------|----------|----------|--------|------|---------|------|
| **Wan2.2-I2V-A14B** | 14B (MoE) | DiT + MoE | 480p/720p | ~24GB | ✅ 네이티브 | 메인 I2V |
| **Wan2.2-TI2V-5B** | 5B | DiT | 480p/720p | ~8GB | ✅ 네이티브 | 대량/저사양 |
| **Wan2.1-VACE-14B** | 14B | DiT | 480p/720p | ~24GB | ✅ 네이티브 | R2V/V2V/편집 |
| Wan2.1-I2V-14B (이전) | 14B | DiT | 480p/720p | ~24GB | ✅ | 레거시 |
| LTXVideo | — | DiT | 768×512 | ~12GB | ✅ | 경량/B-roll |
| SkyReels V1 | — | DiT | 544×960 | ~16GB | ✅ | 시네마틱 |

### 비디오 생성 모델 (클라우드 API 전용, 비설치형)

| 모델 | 제공사 | 해상도 | 오디오 | Multi-shot | 비용 |
|------|--------|--------|--------|-----------|------|
| **Seedance 1.5 Pro** | ByteDance | 1080p | ✅ Joint | ✅ 네이티브 | ~$0.18/클립 |
| **Seedance 2.0** | ByteDance | 2K | ✅ Joint | ✅ 네이티브 | TBD |
| Sora 2 | OpenAI | — | ✅ | ✅ | 구독 기반 |
| Veo 3.1 | Google | — | ✅ | — | API |
| Kling 2.1+ | Kuaishou | 1080p | — | — | API |

### 이미지 생성 모델

| 모델 | 제공사 | 강점 | 비용 | 비고 |
|------|--------|------|------|------|
| **Nano Banana Pro** | Google (Gemini 3) | 캐릭터 일관성, 속도 | ~$0.02/img | **기본 권장** |
| **FLUX.2 [max]** | Black Forest Labs | 4MP, 정밀 제어 | ~$0.03/img | 고품질 fallback |
| Seedream 4.0/4.5 | ByteDance | 스타일라이즈 | ~$0.02/img | 스타일 특화 |
| GPT Image 1.5 | OpenAI | 3D/스타일 변환 | ~$0.04~0.12/img | 특수 용도 |

---

## 부록 B: 용어집

| 용어 | 설명 |
|------|------|
| **I2V** | Image-to-Video. 정지 이미지를 입력으로 영상 생성 |
| **T2V** | Text-to-Video. 텍스트 프롬프트로 영상 생성 |
| **FLF2V** | First-Last Frame to Video. 시작/끝 프레임을 고정하고 중간 영상 생성 |
| **VACE** | Video All-in-One Creation and Editing. Wan2.1의 통합 비디오 편집 모델 |
| **R2V** | Reference-to-Video. 참조 이미지 기반 비디오 생성 (VACE 모드) |
| **V2V** | Video-to-Video. 기존 비디오를 변환 (VACE 모드) |
| **MV2V** | Masked Video-to-Video. 마스크 기반 부분 편집 (VACE 모드) |
| **MoE** | Mixture-of-Experts. Wan2.2의 핵심 아키텍처 |
| **DiT** | Diffusion Transformer |
| **Lightning LoRA** | 4-step 생성을 가능하게 하는 가속 LoRA |
| **TeaCache** | Wan2.1의 ~30% 추론 가속 기법 |
| **QC** | Quality Control. 자동 품질 판정 |
| **SSIM** | Structural Similarity Index. 프레임 간 구조적 유사도 |

---

*문서 끝. 다음 단계로 실행 가능한 패키지(Shot JSON 스키마 예시, ComfyUI 워크플로우 템플릿, Worker 설계) 진행 가능.*