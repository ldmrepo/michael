# SHORTS-COMFYUI-SYS-003: ComfyUI 기반 Shorts 영상 생성 시스템

| 항목 | 내용 |
|------|------|
| **문서 ID** | SHORTS-COMFYUI-SYS-003 |
| **버전** | v1.0.0 |
| **작성일** | 2026-02-07 |
| **이전 버전** | [SHORTS-AUTO-SYS-002](./SHORTS-AUTO-SYS-002.md) |
| **상태** | Draft |

---

## 1. 배경과 목적

### 1.1 현재 문제

기존 youtube-shorts 스킬은 **Veo 3.1**(Google Vertex AI)을 사용하여 영상을 생성한다.

- **Veo 비용**: 약 $0.40/초 — 6초 클립 1개당 ~$2.40
- **60초 Shorts (8 클립)**: ~$19.20/편
- **월 20편 제작 시**: ~$384/월

이 비용은 개인 프로젝트로서 지속 불가능하다.

### 1.2 대안: ComfyUI + Wan2.2

오픈소스 **Wan2.2** 모델을 **ComfyUI**에서 실행하고, **Vast.ai** GPU 클라우드를 활용하면:

- **ComfyUI 비용**: RTX 4090 기준 ~$0.02-0.05/초 (GPU 사용 시간 기준)
- **60초 Shorts (8 클립)**: ~$0.80-2.00/편
- **월 20편 제작 시**: ~$16-40/월

**비용 절감: 90-97%**

### 1.3 SYS-002와의 관계

| SYS-002 | SYS-003 (본 문서) |
|---------|-------------------|
| 독립 시스템 (FastAPI+Redis+PostgreSQL) | **기존 Michael 시스템에 통합** |
| 추상적 아키텍처 설계 | **구체적 코드 확장 지점** (함수명, 라인 번호) |
| 전체 프로덕션 시스템 | **Phase 1 실행 가능한 최소 범위** |
| ComfyUI 실행 방법 미기술 | **Vast.ai Serverless/On-Demand 구체적 API** |

SYS-002는 참조 아키텍처 문서로 보존하고, 본 문서(SYS-003)가 실제 구현 가이드가 된다.

---

## 2. 목표 / 비목표

### 2.1 목표 (Phase 1)

1. `generate-video.py`에 `comfyui` 프로바이더 추가
2. Vast.ai Serverless를 통한 ComfyUI 워크플로우 실행
3. Wan2.2-TI2V-5B / Wan2.2-I2V-A14B 모델 지원 (환경변수 선택)
4. I2V용 컷 이미지 생성 (FLUX.2 Klein 4B 또는 Imagen 4 Fast)
5. 기존 파이프라인(`agentic_video.py` → `add-audio.py` → `upload-youtube.py`) 그대로 유지
6. Telegram UX: 대기 시간 안내 + 진행 상태

### 2.2 비목표

- 독립 API 서버 구축 (FastAPI 등)
- Redis/PostgreSQL 등 추가 인프라
- VACE R2V / FLF2V 워크플로우 (Phase 2+)
- 자동 업로드 스케줄링
- 다중 GPU 병렬 처리
- 프레임 보간 / 업스케일링

---

## 3. 기존 시스템 통합 아키텍처

### 3.1 현재 메시지 흐름

```
User (Telegram)
  │
  ▼
TelegramChannel (src/channels/telegram.ts)
  │  WebSocket
  ▼
Gateway (src/core/gateway.ts, port 18789)
  │
  ▼
ClaudeCodeAgent (src/agent/claude-code.ts)
  │  spawn('claude', ['-p'])
  ▼
Claude Code CLI
  │  "youtube-shorts" 스킬 호출
  ▼
SKILL.md (.claude/skills/youtube-shorts/SKILL.md)
  │  Bash(python3:*)
  ▼
agentic_video.py → generate-video.py → add-audio.py → upload-youtube.py
```

### 3.2 변경 후 메시지 흐름 (ComfyUI 프로바이더 추가)

```
User: "우주 탐험 쇼츠 만들어줘"
  │
  ▼
TelegramChannel → Gateway → ClaudeCodeAgent → Claude CLI
  │
  ▼ SKILL.md에 의해 python3 호출
  │
agentic_video.py --provider comfyui
  │
  ├─ [1/5] generate_continuity_table()  → Claude CLI
  ├─ [2/5] generate_beat_sheet()        → Claude CLI
  ├─ [3/5] generate_shot_list()         → Claude CLI
  ├─ [4/5] generate_clip() × 7-8회     → generate-video.py --provider comfyui
  │         │
  │         ├─ generate_cut_image()      → FLUX.2 Klein 4B (ComfyUI) 또는
  │         │                              Imagen 4 Fast (Google API)
  │         └─ generate_video_comfyui()  → Wan2.2 I2V (ComfyUI)
  │              │
  │              └─ Vast.ai Serverless API
  │                   └─ ComfyUI Worker (RTX 4090)
  │
  └─ [5/5] concat_clips()              → FFmpeg (로컬)
       │
       ▼
  add-audio.py (기존 TTS 파이프라인)
       │
       ▼
  upload-youtube.py (기존 업로드)
```

### 3.3 변경 범위 요약

| 파일 | 변경 유형 | 설명 |
|------|-----------|------|
| `scripts/youtube-shorts/generate-video.py` | **수정** | `generate_video_comfyui()` 함수 추가 (L428-452 router 수정) |
| `scripts/youtube-shorts/agentic_video.py` | **수정** | Shot 데이터클래스 확장, provider "comfyui" 전달 |
| `scripts/youtube-shorts/comfyui_client.py` | **신규** | Vast.ai Serverless + ComfyUI API 클라이언트 |
| `scripts/youtube-shorts/workflows/` | **신규** | ComfyUI 워크플로우 JSON 템플릿 |
| `.claude/skills/youtube-shorts/SKILL.md` | **수정** | comfyui 프로바이더 설명 추가 |

---

## 4. 기존 코드 확장 설계

### 4.1 `generate-video.py` 확장

#### 신규 Configuration (L32 부근 추가)

```python
# ComfyUI 설정 (Vast.ai)
COMFYUI_MODEL = os.environ.get("COMFYUI_MODEL", "wan22-i2v-a14b")  # wan22-i2v-a14b | wan22-ti2v-5b
COMFYUI_STEPS = int(os.environ.get("COMFYUI_STEPS", "20"))
COMFYUI_CFG = float(os.environ.get("COMFYUI_CFG", "3.5"))
COMFYUI_RESOLUTION = os.environ.get("COMFYUI_RESOLUTION", "720x1280")  # WxH (9:16 세로형, 14B 기본)
COMFYUI_FRAMES = int(os.environ.get("COMFYUI_FRAMES", "121"))  # 121 frames ≈ 5s @24fps

# 컷 이미지 생성 프로바이더
CUT_IMAGE_PROVIDER = os.environ.get("CUT_IMAGE_PROVIDER", "gemini")  # gemini | flux
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")  # Google API 키 — Imagen 4 Fast (gemini 프로바이더 사용 시 필수)
```

#### 신규 함수: `generate_video_comfyui()`

```python
def generate_video_comfyui(
    prompt: str,
    duration: int = 8,
    output_path: str = "/tmp/shorts/video.mp4",
    aspect_ratio: str = "9:16",
    input_image: Optional[str] = None,
) -> Optional[str]:
    """Generate video using ComfyUI via Vast.ai Serverless.

    Args:
        prompt: Text prompt describing the video
        duration: Video duration in seconds (mapped to frame count)
        output_path: Path to save the generated video
        aspect_ratio: Video aspect ratio (9:16 for shorts)
        input_image: Optional input image path for I2V mode

    Returns:
        Output path if successful, None otherwise
    """
    from comfyui_client import ComfyUIClient

    client = ComfyUIClient()

    # Step 1: I2V 모드인 경우 컷 이미지 생성
    if input_image is None and COMFYUI_MODEL != "wan22-ti2v-5b":  # 14B(기본)는 I2V 전용 → 항상 컷 이미지 필요
        provider_name = "Imagen 4" if CUT_IMAGE_PROVIDER == "gemini" else "FLUX.2 Klein"
        print(f"🖼️ Generating cut image with {provider_name}...")
        input_image = client.generate_cut_image(prompt, 480, 832)
        if input_image is None:
            print("⚠️ Image generation failed, falling back to T2V")

    # Step 2: 프레임 수 계산
    fps = 24
    frames = min(duration * fps, 169)  # Max 169 frames for Wan2.2
    # Wan2.2는 (4k+1) 프레임 필요: 97, 121, 145, 169
    valid_frames = [97, 121, 145, 169]
    frames = min(valid_frames, key=lambda x: abs(x - frames))

    # Step 3: 해상도 결정
    if aspect_ratio == "9:16":
        width, height = (480, 832) if "5b" in COMFYUI_MODEL else (720, 1280)
    elif aspect_ratio == "16:9":
        width, height = (832, 480) if "5b" in COMFYUI_MODEL else (1280, 720)
    else:
        width, height = (640, 640) if "5b" in COMFYUI_MODEL else (960, 960)

    # Step 4: ComfyUI 워크플로우 실행
    print(f"🎬 Generating video with ComfyUI (Wan2.2)...")
    print(f"   Model: {COMFYUI_MODEL}")
    print(f"   Resolution: {width}x{height}")
    print(f"   Frames: {frames} ({frames/fps:.1f}s @{fps}fps)")
    print(f"   Mode: {'I2V' if input_image else 'T2V'}")

    result = client.generate_video(
        prompt=prompt,
        width=width,
        height=height,
        frames=frames,
        steps=COMFYUI_STEPS,
        cfg=COMFYUI_CFG,
        model=COMFYUI_MODEL,
        input_image=input_image,
    )

    if result:
        # 비디오 다운로드 및 저장
        client.download_result(result, output_path)
        print(f"✅ Video saved: {output_path}")
        return output_path

    print("❌ ComfyUI video generation failed")
    return None
```

#### Router 수정 (L428-452)

현재:
```python
def generate_video(prompt, duration=8, output_path=..., aspect_ratio=..., provider=None):
    provider = provider or DEFAULT_PROVIDER
    if provider.lower() == "sora":
        return generate_video_sora(...)
    else:
        return generate_video_veo(...)
```

변경 후:
```python
def generate_video(prompt, duration=8, output_path=..., aspect_ratio=..., provider=None):
    provider = provider or DEFAULT_PROVIDER
    if provider.lower() == "sora":
        return generate_video_sora(...)
    elif provider.lower() == "comfyui":
        return generate_video_comfyui(...)
    else:
        return generate_video_veo(...)
```

### 4.2 `agentic_video.py` 확장

#### Shot 데이터클래스 확장 (L37-63)

```python
@dataclass
class Shot:
    """8-Point Shot Grammar"""
    id: int
    subject: str
    emotion: str
    optics: str
    motion: str
    lighting: str
    style: str
    audio: str
    continuity: str
    duration: int = 8
    rendering_hint: str = "i2v"       # 신규: i2v, t2v, flf2v (Phase 2)
    reference_image: str = ""          # 신규: I2V 레퍼런스 이미지 경로

    def __post_init__(self):
        """Normalize duration to valid values per provider"""
        VEO_DURATIONS = [4, 6, 8]
        COMFYUI_DURATIONS = [4, 5, 6, 7]  # frames: 97, 121, 145, 169 @24fps
        # Duration normalization은 provider에 따라 generate_clip()에서 처리
```

#### CLI 확장 (L611 부근)

```python
parser.add_argument(
    "--provider", "-p",
    choices=["veo", "sora", "comfyui"],  # comfyui 추가
    default=None,
    help="Video provider: veo (default), sora, or comfyui"
)
```

### 4.3 SKILL.md 업데이트

```markdown
## 프로바이더 선택

| 프로바이더 | 비용 | 품질 | 속도 | 비고 |
|-----------|------|------|------|------|
| **veo** (기본) | ~$2.40/clip | 최고 | ~2분 | Veo 3.1 네이티브 오디오 |
| **sora** | ~$2/clip | 높음 | ~3분 | OpenAI API 키 필요 |
| **comfyui** | ~$0.10-0.25/clip | 좋음 | ~3-5분 | Vast.ai GPU, 비용 최적 |

환경변수로 기본 프로바이더 설정:
\`\`\`bash
VIDEO_PROVIDER=comfyui    # comfyui 사용
COMFYUI_MODEL=wan22-i2v-a14b  # 고품질 14B 모델 (기본값)
# COMFYUI_MODEL=wan22-ti2v-5b  # 저비용 5B 모델
\`\`\`
```

---

## 5. Vast.ai 인스턴스 관리

### 5.1 Phase 1: Serverless 모드

Vast.ai Serverless는 요청 시에만 GPU를 사용하고, 유휴 시 비용이 발생하지 않는다.

#### 아키텍처

```
comfyui_client.py
  │  vastai-sdk (Python)
  ▼
Vast.ai Serverless Router
  │  Auto-selects best worker
  ▼
ComfyUI Worker Pool (RTX 4090)
  │  PyWorker → ComfyUI Server
  ▼
comfyui_client.py (GET /view로 결과물 직접 다운로드 → 로컬 저장)
```

#### Serverless 엔드포인트 호출

```python
# scripts/youtube-shorts/comfyui_client.py

import asyncio
import json
import os
import urllib.request
from typing import Optional

# Vast.ai Serverless SDK
from vastai import Serverless


class ComfyUIClient:
    """ComfyUI client via Vast.ai Serverless (Phase 1) or On-Demand (Phase 2)"""

    ENDPOINT_NAME = "comfyui-json"  # Vast.ai 기본 ComfyUI 엔드포인트

    def __init__(self, comfyui_host: Optional[str] = None):
        self.api_key = os.environ.get("VAST_API_KEY")
        if not self.api_key:
            raise ValueError("VAST_API_KEY 환경변수가 필요합니다")
        # Serverless: None (SDK 응답에 포함된 URL 사용)
        # On-Demand: "http://<ip>:<port>" (직접 ComfyUI API 접근)
        self.comfyui_host = comfyui_host

    async def _submit_workflow(self, workflow: dict) -> dict:
        """Submit ComfyUI workflow to Vast.ai Serverless"""
        async with Serverless() as client:
            endpoint = await client.get_endpoint(name=self.ENDPOINT_NAME)
            result = await endpoint.request(
                "/comfyui/workflow",
                workflow,
                cost=100.0,  # ComfyUI 요청당 고정 비용 단위
            )
            return result

    def generate_video(
        self,
        prompt: str,
        width: int,
        height: int,
        frames: int,
        steps: int = 20,
        cfg: float = 3.5,
        model: str = "wan22-i2v-a14b",
        input_image: Optional[str] = None,
    ) -> Optional[dict]:
        """Generate video via ComfyUI workflow"""
        workflow = self._build_video_workflow(
            prompt, width, height, frames, steps, cfg, model, input_image
        )
        try:
            result = asyncio.run(self._submit_workflow(workflow))
            return result
        except Exception as e:
            print(f"❌ Vast.ai error: {e}")
            return None

    def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "9:16",
        output_path: str = "/tmp/shorts/cut.png",
    ) -> Optional[str]:
        """Generate image via FLUX.2 Klein 4B workflow"""
        workflow = self._build_image_workflow(prompt, aspect_ratio)
        try:
            result = asyncio.run(self._submit_workflow(workflow))
            # 결과에서 파일명/URL 추출 후 다운로드
            if result and "images" in result:
                img = result["images"][0]
                # Serverless: URL 포함 / On-Demand: filename만 포함
                url_or_filename = img.get("url") or img.get("filename")
                return self._download_output(url_or_filename, output_path)
            return None
        except Exception as e:
            print(f"❌ Image generation error: {e}")
            return None

    def download_result(self, result: dict, output_path: str) -> str:
        """Download result from ComfyUI output"""
        # Serverless: URL 포함 / On-Demand: filename만 포함
        video = result.get("videos", [{}])[0] if "videos" in result else result
        url_or_filename = video.get("url") or video.get("filename")
        if not url_or_filename:
            raise ValueError("No output filename/url in result")
        return self._download_output(url_or_filename, output_path)

    def _download_output(self, filename_or_url: str, output_path: str) -> str:
        """Download file from ComfyUI output to local path.

        Args:
            filename_or_url: Serverless 모드에서는 SDK 응답의 download URL,
                             On-Demand 모드에서는 filename (self.comfyui_host + /view 사용)
            output_path: 로컬 저장 경로
        """
        if filename_or_url.startswith("http"):
            # Serverless: SDK 응답에 포함된 full URL (Vast.ai가 제공)
            url = filename_or_url
        elif self.comfyui_host:
            # On-Demand: 인스턴스의 ComfyUI /view 엔드포인트
            url = f"{self.comfyui_host}/view?filename={filename_or_url}&type=output"
        else:
            raise ValueError(
                "Serverless 모드에서는 download URL이 필요합니다. "
                "On-Demand 모드에서는 comfyui_host를 설정하세요."
            )
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        urllib.request.urlretrieve(url, output_path)
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"📥 Downloaded: {output_path} ({size_mb:.2f} MB)")
        return output_path

    # Workflow builders는 Section 6에서 상세 설명
    def _build_video_workflow(self, ...): ...
    def _build_image_workflow(self, ...): ...
```

#### 환경변수

```bash
VAST_API_KEY=xxxxxxxxxxxxxxxx           # Vast.ai API 키
```

### 5.2 Phase 2: On-Demand 모드

대량 생산 시 Serverless보다 On-Demand가 비용 효율적일 수 있다.

#### 인스턴스 생명주기

```
생성(create) → 대기(ready) → 작업(working) → 파괴(destroy)
     │                           │
     └── 시작 시 모델 로딩 (3-5분) ──┘
```

#### On-Demand 인스턴스 관리 API

```python
class VastOnDemandManager:
    """Vast.ai On-Demand instance lifecycle manager"""

    BASE_URL = "https://console.vast.ai/api/v0"
    DOCKER_IMAGE = "ghcr.io/ai-dock/comfyui:latest-cuda"

    def __init__(self):
        self.api_key = os.environ.get("VAST_API_KEY")
        self.instance_id = None

    def find_gpu(self, gpu_name: str = "RTX_4090", min_vram: int = 24) -> Optional[dict]:
        """Search for available GPU offers"""
        # POST /bundles/
        data = {
            "verified": {"eq": True},
            "rentable": {"eq": True},
            "gpu_name": {"eq": gpu_name},
            "gpu_ram": {"gte": min_vram * 1024},  # MB
            "reliability": {"gte": 0.95},
        }
        response = self._api_request("POST", "/bundles/", data)
        offers = response.get("offers", [])
        # 가격순 정렬
        offers.sort(key=lambda x: x.get("dph_total", float("inf")))
        return offers[0] if offers else None

    def create_instance(self, offer_id: int) -> str:
        """Create GPU instance with ComfyUI"""
        # PUT /asks/{offer_id}/
        data = {
            "image": self.DOCKER_IMAGE,
            "disk": 50,  # GB (모델 저장용)
            "env": {
                "COMFYUI_ARGS": "--gpu-only --highvram",
                "HF_TOKEN": os.environ.get("HF_TOKEN", ""),
            },
        }
        response = self._api_request("PUT", f"/asks/{offer_id}/", data)
        self.instance_id = response.get("new_contract")
        return self.instance_id

    def destroy_instance(self):
        """Destroy instance after use"""
        if self.instance_id:
            # DELETE /instances/{instance_id}/
            self._api_request("DELETE", f"/instances/{self.instance_id}/")
            self.instance_id = None

    def get_instance_url(self) -> Optional[str]:
        """Get ComfyUI URL of running instance"""
        if not self.instance_id:
            return None
        response = self._api_request("GET", f"/instances/{self.instance_id}/")
        # 포트 매핑에서 8188 (ComfyUI) 찾기
        ports = response.get("ports", {})
        if "8188/tcp" in ports:
            host = response.get("public_ipaddr")
            port = ports["8188/tcp"][0]["HostPort"]
            return f"http://{host}:{port}"
        return None

    def _api_request(self, method: str, path: str, data: dict = None) -> dict:
        """Make Vast.ai API request"""
        url = f"{self.BASE_URL}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        req = urllib.request.Request(url, headers=headers, method=method)
        if data:
            req.data = json.dumps(data).encode("utf-8")
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
```

#### On-Demand vs Serverless 비교

| 항목 | Serverless | On-Demand |
|------|-----------|-----------|
| 시작 시간 | 3-30초 (warm) / 3-5분 (cold) | 3-5분 (항상 cold start) |
| 유휴 비용 | 없음 | GPU 시간당 과금 |
| 적합 시나리오 | 간헐적 (1-5편/일) | 대량 (10편+ 연속) |
| 모델 로딩 | 자동 (캐싱됨) | 매번 필요 (또는 인스턴스 유지) |
| 구현 복잡도 | 낮음 | 높음 (생명주기 관리) |

**권장**: Phase 1은 Serverless로 시작하고, 일일 생산량이 10편 이상이면 On-Demand 추가.

---

## 6. ComfyUI 워크플로우 설계

### 6.1 Wan2.2 모델 구성

#### 지원 모델

| 모델 | 파라미터 | VRAM | 해상도 | 용도 |
|------|---------|------|--------|------|
| **Wan2.2-TI2V-5B** | 5B | ~8GB | 480×832 | T2V + I2V 겸용, 대량 생산 |
| **Wan2.2-I2V-A14B** | 14B (MoE) | ~24GB | 720×1280 | I2V 전용, 고품질 |

#### 필요 모델 파일

```
models/diffusion_models/
  ├── wan2.2_ti2v_5B_fp16.safetensors              # TI2V-5B
  ├── wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors  # I2V-A14B (Pass 1)
  └── wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors   # I2V-A14B (Pass 2)

models/text_encoders/
  ├── umt5_xxl_fp8_e4m3fn_scaled.safetensors       # Wan2.2 공용 텍스트 인코더
  ├── clip_l.safetensors                            # FLUX.2 Klein CLIP-L
  └── qwen_3_4b.safetensors                        # FLUX.2 Klein Qwen3-4B

models/vae/
  ├── wan2.2_vae.safetensors                        # 5B용 VAE
  ├── wan_2.1_vae.safetensors                       # 14B용 VAE
  └── flux2-vae.safetensors                         # FLUX.2 VAE

models/diffusion_models/
  └── flux-2-klein-4b-fp8.safetensors               # FLUX.2 Klein 4B (fp8)
```

#### 환경변수로 모델 선택

```bash
# 기본값: 14B MoE (고품질)
COMFYUI_MODEL=wan22-i2v-a14b

# 저비용: 5B (빠르고 저렴)
# COMFYUI_MODEL=wan22-ti2v-5b
```

### 6.2 TI2V-5B 워크플로우 (Single-Pass)

`scripts/youtube-shorts/workflows/wan22_ti2v_5b.json`

```json
{
  "1": {
    "class_type": "UNETLoader",
    "inputs": {
      "unet_name": "wan2.2_ti2v_5B_fp16.safetensors",
      "weight_dtype": "fp8_e4m3fn_fast"
    },
    "_meta": {"title": "Load Wan2.2 TI2V-5B (fp16 모델을 fp8로 양자화 로딩 — VRAM 절약, 속도 향상)"}
  },
  "2": {
    "class_type": "CLIPLoader",
    "inputs": {
      "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
      "type": "wan"
    },
    "_meta": {"title": "Load Text Encoder"}
  },
  "3": {
    "class_type": "VAELoader",
    "inputs": {
      "vae_name": "wan2.2_vae.safetensors"
    },
    "_meta": {"title": "Load VAE"}
  },
  "4": {
    "class_type": "CLIPTextEncode",
    "inputs": {
      "text": "{{PROMPT}}",
      "clip": ["2", 0]
    },
    "_meta": {"title": "Positive Prompt"}
  },
  "5": {
    "class_type": "CLIPTextEncode",
    "inputs": {
      "text": "blurry, distorted, low quality, watermark, text, deformed",
      "clip": ["2", 0]
    },
    "_meta": {"title": "Negative Prompt"}
  },
  "6": {
    "class_type": "LoadImage",
    "inputs": {
      "image": "{{INPUT_IMAGE}}"
    },
    "_meta": {"title": "Input Image (I2V)"}
  },
  "7": {
    "class_type": "Wan2.2ImageToVideoLatent",
    "inputs": {
      "width": 480,
      "height": 832,
      "length": 121,
      "batch_size": 1,
      "image": ["6", 0],
      "vae": ["3", 0]
    },
    "_meta": {"title": "I2V Latent (5B) — 9:16 세로형 Shorts"}
  },
  "8": {
    "class_type": "KSampler",
    "inputs": {
      "seed": "__RANDOM_INT__",
      "steps": 20,
      "cfg": 3.5,
      "sampler_name": "euler",
      "scheduler": "beta",
      "denoise": 1.0,
      "model": ["1", 0],
      "positive": ["4", 0],
      "negative": ["5", 0],
      "latent_image": ["7", 0]
    },
    "_meta": {"title": "KSampler"}
  },
  "9": {
    "class_type": "VAEDecode",
    "inputs": {
      "samples": ["8", 0],
      "vae": ["3", 0]
    },
    "_meta": {"title": "VAE Decode"}
  },
  "10": {
    "class_type": "VHS_VideoCombine",
    "inputs": {
      "frame_rate": 24,
      "loop_count": 0,
      "filename_prefix": "wan22_output",
      "format": "video/h264-mp4",
      "images": ["9", 0]
    },
    "_meta": {"title": "Save Video"}
  }
}
```

**T2V 모드** (이미지 없이): 노드 "6"(LoadImage)과 "7"(Wan2.2ImageToVideoLatent)를 `EmptyHunyuanLatentVideo`로 대체:

```json
{
  "7": {
    "class_type": "EmptyHunyuanLatentVideo",
    "inputs": {
      "width": 480,
      "height": 832,
      "length": 121,
      "batch_size": 1
    }
  }
}
```

### 6.3 I2V-A14B 워크플로우 (2-Pass MoE)

`scripts/youtube-shorts/workflows/wan22_i2v_a14b.json`

**핵심**: 14B 모델은 MoE(Mixture of Experts) 아키텍처로, High-Noise Expert와 Low-Noise Expert가 별도 모델이다.

```json
{
  "1": {
    "class_type": "UNETLoader",
    "inputs": {
      "unet_name": "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors",
      "weight_dtype": "fp8_e4m3fn_fast"
    },
    "_meta": {"title": "High Noise Expert (Pass 1)"}
  },
  "2": {
    "class_type": "UNETLoader",
    "inputs": {
      "unet_name": "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
      "weight_dtype": "fp8_e4m3fn_fast"
    },
    "_meta": {"title": "Low Noise Expert (Pass 2)"}
  },
  "3": {
    "class_type": "CLIPLoader",
    "inputs": {
      "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
      "type": "wan"
    },
    "_meta": {"title": "Load Text Encoder"}
  },
  "4": {
    "class_type": "VAELoader",
    "inputs": {
      "vae_name": "wan_2.1_vae.safetensors"
    },
    "_meta": {"title": "Load VAE (14B)"}
  },
  "5": {
    "class_type": "CLIPTextEncode",
    "inputs": {
      "text": "{{PROMPT}}",
      "clip": ["3", 0]
    },
    "_meta": {"title": "Positive Prompt"}
  },
  "6": {
    "class_type": "CLIPTextEncode",
    "inputs": {
      "text": "blurry, distorted, low quality, watermark, text, deformed",
      "clip": ["3", 0]
    },
    "_meta": {"title": "Negative Prompt"}
  },
  "7": {
    "class_type": "LoadImage",
    "inputs": {
      "image": "{{INPUT_IMAGE}}"
    },
    "_meta": {"title": "Input Image"}
  },
  "8": {
    "class_type": "Wan2.2ImageToVideoLatent",
    "inputs": {
      "width": 720,
      "height": 1280,
      "length": 121,
      "batch_size": 1,
      "image": ["7", 0],
      "vae": ["4", 0]
    },
    "_meta": {"title": "I2V Latent (14B) — LoadImage를 VAE 인코딩하여 latent 생성"}
  },
  "10": {
    "class_type": "KSamplerAdvanced",
    "inputs": {
      "add_noise": "enable",
      "noise_seed": "__RANDOM_INT__",
      "steps": 20,
      "cfg": 3.5,
      "sampler_name": "euler",
      "scheduler": "beta",
      "start_at_step": 0,
      "end_at_step": 10,
      "return_with_leftover_noise": "enable",
      "model": ["1", 0],
      "positive": ["5", 0],
      "negative": ["6", 0],
      "latent_image": ["8", 0]
    },
    "_meta": {"title": "Pass 1: High Noise (steps 0-10)"}
  },
  "11": {
    "class_type": "KSamplerAdvanced",
    "inputs": {
      "add_noise": "disable",
      "noise_seed": "__RANDOM_INT__",
      "steps": 20,
      "cfg": 3.5,
      "sampler_name": "euler",
      "scheduler": "beta",
      "start_at_step": 10,
      "end_at_step": 10000,
      "return_with_leftover_noise": "disable",
      "model": ["2", 0],
      "positive": ["5", 0],
      "negative": ["6", 0],
      "latent_image": ["10", 0]
    },
    "_meta": {"title": "Pass 2: Low Noise (steps 10+)"}
  },
  "12": {
    "class_type": "VAEDecode",
    "inputs": {
      "samples": ["11", 0],
      "vae": ["4", 0]
    },
    "_meta": {"title": "VAE Decode"}
  },
  "13": {
    "class_type": "VHS_VideoCombine",
    "inputs": {
      "frame_rate": 24,
      "loop_count": 0,
      "filename_prefix": "wan22_a14b_output",
      "format": "video/h264-mp4",
      "images": ["12", 0]
    },
    "_meta": {"title": "Save Video"}
  }
}
```

**2-Pass 핵심 설정**:

| Pass | Model | add_noise | start_at_step | end_at_step | return_with_leftover_noise |
|------|-------|-----------|---------------|-------------|---------------------------|
| **1 (High Noise)** | high_noise_14B | enable | 0 | 10 | enable |
| **2 (Low Noise)** | low_noise_14B | disable | 10 | 10000 | disable |

- 총 steps: 20 (Pass 1: 0-10, Pass 2: 10-20)
- CFG: 3.5 (양쪽 동일)
- Sampler: euler, Scheduler: beta
- **denoise는 낮추지 않는다** — I2V에서 denoise < 1.0은 소스 이미지를 보존하지 못함

### 6.4 워크플로우 JSON 파라미터화

```python
# comfyui_client.py 내부

import random
from pathlib import Path

WORKFLOW_DIR = Path(__file__).parent / "workflows"


def _load_workflow(name: str) -> dict:
    """Load workflow JSON template"""
    path = WORKFLOW_DIR / f"{name}.json"
    with open(path) as f:
        return json.load(f)


def _parameterize_workflow(
    workflow: dict,
    prompt: str,
    width: int,
    height: int,
    frames: int,
    steps: int,
    cfg: float,
    seed: Optional[int] = None,
    input_image: Optional[str] = None,
) -> dict:
    """Replace placeholders in workflow JSON"""
    wf = json.loads(json.dumps(workflow))  # Deep copy

    for node_id, node in wf.items():
        inputs = node.get("inputs", {})

        # Prompt 치환
        if node["class_type"] == "CLIPTextEncode":
            if "{{PROMPT}}" in inputs.get("text", ""):
                inputs["text"] = prompt

        # Seed 치환 (매번 다른 값)
        for key in ("seed", "noise_seed"):
            if key in inputs:
                if inputs[key] == "__RANDOM_INT__" or seed:
                    inputs[key] = seed or random.randint(0, 2**53)

        # 해상도 / 프레임 수
        if node["class_type"] in ("EmptyHunyuanLatentVideo", "Wan2.2ImageToVideoLatent"):
            inputs["width"] = width
            inputs["height"] = height
            inputs["length"] = frames

        # 이미지 입력
        if node["class_type"] == "LoadImage" and input_image:
            inputs["image"] = input_image

        # Steps / CFG
        if node["class_type"] in ("KSampler", "KSamplerAdvanced"):
            inputs["steps"] = steps
            inputs["cfg"] = cfg
            # 2-Pass: split step 자동 계산
            if node["class_type"] == "KSamplerAdvanced":
                split = steps // 2
                meta_title = node.get("_meta", {}).get("title", "")
                if "Pass 1" in meta_title or "High Noise" in meta_title:
                    inputs["end_at_step"] = split
                elif "Pass 2" in meta_title or "Low Noise" in meta_title:
                    inputs["start_at_step"] = split

    return wf
```

### 6.5 ComfyUI API 호출 패턴

Vast.ai Serverless의 `comfyui-json` 엔드포인트는 내부적으로 다음과 동일하다:

```python
# 직접 ComfyUI API 호출 (On-Demand 모드에서 사용)

def submit_comfyui_workflow(host: str, workflow: dict) -> str:
    """POST /prompt — 워크플로우 제출"""
    url = f"{host}/prompt"
    data = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        return result["prompt_id"]


def poll_comfyui_result(host: str, prompt_id: str, max_wait: int = 600) -> Optional[dict]:
    """GET /history/{prompt_id} — 결과 폴링"""
    url = f"{host}/history/{prompt_id}"
    start = time.time()

    while time.time() - start < max_wait:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if prompt_id in data:
            entry = data[prompt_id]
            status = entry.get("status", {})
            if status.get("completed"):
                return entry.get("outputs", {})
            if status.get("status_str") == "error":
                print(f"❌ ComfyUI error: {entry}")
                return None

        elapsed = int(time.time() - start)
        print(f"⏳ ComfyUI processing... ({elapsed}s)")
        time.sleep(10)

    print(f"❌ Timeout after {max_wait}s")
    return None


def download_comfyui_output(host: str, filename: str, output_path: str) -> str:
    """GET /view — 결과 파일 다운로드"""
    url = f"{host}/view?filename={filename}&type=output"
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    urllib.request.urlretrieve(url, output_path)
    return output_path
```

---

## 7. 컷 이미지 생성

I2V 워크플로우에는 입력 이미지가 필요하다. 두 가지 프로바이더를 지원한다:

| 프로바이더 | 장점 | 단점 | 비용 | 환경변수 |
|-----------|------|------|------|----------|
| **Imagen 4 Fast** (기본) | 고품질, GPU 부담 분리, 빠름 (~2초) | API 비용 발생, API 키 필요 | ~$0.02/장 | `CUT_IMAGE_PROVIDER=gemini` |
| **FLUX.2 Klein 4B** | 추가 비용 없음, ComfyUI 내부 처리 | GPU에 모델 로딩 필요 (~9GB) | $0.003/장 (GPU 시간) | `CUT_IMAGE_PROVIDER=flux` |

```bash
# 환경변수로 선택
CUT_IMAGE_PROVIDER=gemini     # Imagen 4 Fast (Google API, 기본값)
# CUT_IMAGE_PROVIDER=flux     # FLUX.2 Klein 4B (ComfyUI 내부, 저비용)
GOOGLE_API_KEY=AIza...        # gemini 사용 시 필수
```

### 7.1 FLUX.2 Klein 4B 워크플로우

`scripts/youtube-shorts/workflows/flux2_klein_4b.json`

> **변경 이유**: FLUX.1 schnell(12B, ~17GB VRAM, ~3-5초)은 FLUX.2 Klein 4B(4B, **~9GB VRAM, ~1-2초**)로 대체.
> 속도 2배, VRAM 절반, Apache 2.0 라이선스 동일.

```json
{
  "1": {
    "class_type": "UNETLoader",
    "inputs": {
      "unet_name": "flux-2-klein-4b-fp8.safetensors",
      "weight_dtype": "fp8_e4m3fn"
    },
    "_meta": {"title": "Load FLUX.2 Klein 4B"}
  },
  "2": {
    "class_type": "DualCLIPLoader",
    "inputs": {
      "clip_name1": "clip_l.safetensors",
      "clip_name2": "qwen_3_4b.safetensors",
      "type": "flux"
    },
    "_meta": {"title": "Load Text Encoders (CLIP-L + Qwen3-4B)"}
  },
  "3": {
    "class_type": "VAELoader",
    "inputs": {
      "vae_name": "flux2-vae.safetensors"
    },
    "_meta": {"title": "Load VAE (FLUX.2)"}
  },
  "4": {
    "class_type": "CLIPTextEncode",
    "inputs": {
      "text": "{{PROMPT}}",
      "clip": ["2", 0]
    },
    "_meta": {"title": "Positive Prompt"}
  },
  "5": {
    "class_type": "CLIPTextEncode",
    "inputs": {
      "text": "",
      "clip": ["2", 0]
    },
    "_meta": {"title": "Negative Prompt (empty for FLUX)"}
  },
  "6": {
    "class_type": "EmptySD3LatentImage",
    "inputs": {
      "width": 480,
      "height": 832,
      "batch_size": 1
    },
    "_meta": {"title": "Empty Latent (9:16 세로형 Shorts)"}
  },
  "7": {
    "class_type": "KSampler",
    "inputs": {
      "seed": "__RANDOM_INT__",
      "steps": 4,
      "cfg": 1.0,
      "sampler_name": "euler",
      "scheduler": "simple",
      "denoise": 1.0,
      "model": ["1", 0],
      "positive": ["4", 0],
      "negative": ["5", 0],
      "latent_image": ["6", 0]
    },
    "_meta": {"title": "KSampler (4 steps, distilled)"}
  },
  "8": {
    "class_type": "VAEDecode",
    "inputs": {
      "samples": ["7", 0],
      "vae": ["3", 0]
    },
    "_meta": {"title": "VAE Decode"}
  },
  "9": {
    "class_type": "SaveImage",
    "inputs": {
      "filename_prefix": "flux2_cut",
      "images": ["8", 0]
    },
    "_meta": {"title": "Save Image"}
  }
}
```

**FLUX.2 Klein 4B 핵심 설정**:
- Steps: **4** (distilled 모델, 4스텝에 최적화)
- CFG: **1.0** (FLUX는 guidance-distilled, 높이면 품질 저하)
- Negative prompt: **빈 문자열** (FLUX에서는 불필요)
- Latent type: **EmptySD3LatentImage** (EmptyLatentImage가 아님!)
- Text Encoder: **Qwen3-4B** (FLUX.1의 T5-XXL 대체 → VRAM 절약)
- 소요 시간: RTX 4090에서 **~1-2초** (FLUX.1 schnell 대비 2배 빠름)
- VRAM: **~9GB** (FLUX.1의 ~17GB 대비 절반)

### 7.2 이미지→I2V 파이프라인

같은 ComfyUI 인스턴스 내에서 FLUX 출력 → Wan2.2 입력으로 연결:

```python
def generate_cut_and_video(
    self,
    prompt: str,
    video_prompt: str,
    width: int,
    height: int,
    frames: int,
    model: str,
) -> Optional[dict]:
    """2-step: FLUX.2 image → Wan2.2 I2V"""

    # Step 1: FLUX.2로 컷 이미지 생성
    image_wf = self._build_image_workflow(prompt, f"{width}:{height}")
    image_result = asyncio.run(self._submit_workflow(image_wf))

    if not image_result:
        return None

    # FLUX.2 출력 파일명 추출 (ComfyUI 내부 파일시스템)
    image_filename = image_result.get("images", [{}])[0].get("filename")

    # Step 2: Wan2.2 I2V로 비디오 생성
    video_wf = self._build_video_workflow(
        prompt=video_prompt,
        width=width,
        height=height,
        frames=frames,
        input_image=image_filename,
    )
    return asyncio.run(self._submit_workflow(video_wf))
```

> **참고**: Vast.ai Serverless에서는 같은 엔드포인트의 워커가 공유 파일시스템을 사용하므로, FLUX.2 `SaveImage` 출력 파일명을 Wan2.2 `LoadImage`에 직접 전달 가능.

### 7.3 Imagen 4 Fast 이미지 생성

Google Imagen 4 Fast를 활용하여 컷 이미지를 생성한다.
FLUX.2 대비 **GPU 부담 분리** (외부 API로 처리)되고, **고품질 이미지**를 ~2초 내에 생성할 수 있다.

> **변경 이유**: 기존 gemini-2.0-flash-exp는 2025.11 deprecated, 2026.03 완전 퇴출 예정.
> Imagen 4 Fast는 후속 이미지 생성 모델로, 동일 Google API 키 사용, $0.02/장.

#### API 호출 패턴

```python
import base64

def generate_image_gemini(
    prompt: str,
    width: int = 480,
    height: int = 832,
    output_path: str = "/tmp/shorts/cut.png",
) -> Optional[str]:
    """Generate cut image using Google Imagen 4 Fast.

    Args:
        prompt: Image description prompt
        width: Image width (aspect ratio 계산용)
        height: Image height (aspect ratio 계산용)
        output_path: Path to save the generated image

    Returns:
        Output path if successful, None otherwise
    """
    if not GOOGLE_API_KEY:
        print("❌ GOOGLE_API_KEY 환경변수가 필요합니다 (Imagen 4 Fast)")
        return None

    # Aspect ratio 계산 (9:16 세로형 Shorts)
    aspect_ratio = "9:16" if width < height else "16:9"

    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"imagen-4-fast:generateImages?key={GOOGLE_API_KEY}"
    )

    request_body = {
        "prompt": f"High-quality cinematic image: {prompt}. "
                  f"Style: photorealistic, cinematic lighting, film grain.",
        "config": {
            "numberOfImages": 1,
            "aspectRatio": aspect_ratio,
        }
    }

    headers = {"Content-Type": "application/json"}

    print(f"🖼️ Generating cut image with Imagen 4 Fast...")
    print(f"   Prompt: {prompt[:60]}...")
    print(f"   Aspect ratio: {aspect_ratio}")

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(request_body).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"❌ Imagen 4 Fast API Error: {e.code}")
        print(f"   Details: {error_body[:300]}")
        return None

    # 이미지 데이터 추출 (base64)
    try:
        images = data["generatedImages"]
        image_data = images[0]["image"]["imageBytes"]
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(base64.b64decode(image_data))
        print(f"✅ Cut image saved: {output_path}")
        return output_path
    except (KeyError, IndexError) as e:
        print(f"❌ Failed to parse Imagen 4 Fast response: {e}")
        return None

    return None
```

#### 프로바이더 라우터 (comfyui_client.py)

```python
def generate_cut_image(
    self,
    prompt: str,
    width: int = 480,
    height: int = 832,
    output_path: str = "/tmp/shorts/cut.png",
) -> Optional[str]:
    """Generate cut image using configured provider"""
    provider = CUT_IMAGE_PROVIDER

    if provider == "flux":
        return self.generate_image(prompt, f"{width}:{height}")
    else:  # gemini (기본값)
        return generate_image_gemini(prompt, width, height, output_path)
```

#### Imagen 4 Fast 이미지 → ComfyUI I2V 연결

Imagen 4 Fast로 생성한 이미지는 로컬 파일로 저장된다. ComfyUI에 전달하려면 `/upload/image` 엔드포인트로 업로드:

```python
def upload_image_to_comfyui(host: str, image_path: str) -> str:
    """Upload local image to ComfyUI instance for I2V input"""
    url = f"{host}/upload/image"
    filename = os.path.basename(image_path)

    # Multipart form data
    boundary = "----FormBoundary" + str(random.randint(10**9, 10**10))
    with open(image_path, "rb") as f:
        image_data = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode() + image_data + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        return result.get("name", filename)  # ComfyUI 내부 파일명 반환
```

---

## 8. 후처리

기존 `add-audio.py`와 FFmpeg 파이프라인을 **그대로 재사용**한다.

### 8.1 기존 파이프라인 (변경 없음)

```
concat_clips() (agentic_video.py:342)
  │  FFmpeg xfade transitions
  ▼
add-audio.py
  ├─ generate_tts()      → OpenAI TTS API (tts-1, voice: nova)
  ├─ merge_audio_video()  → FFmpeg filter_complex
  └─ 출력: final_with_audio.mp4
```

### 8.2 ComfyUI 특이사항

| 항목 | Veo 3.1 | ComfyUI (Wan2.2) |
|------|---------|-------------------|
| 출력 해상도 | 1080p | 480p (5B) / 720p (14B) |
| 출력 FPS | 24fps | 24fps |
| 내장 오디오 | 있음 (Veo 네이티브) | **없음** → TTS/BGM 필수 |
| 코덱 | H.264 | H.264 (VHS_VideoCombine) |
| 총 길이 | 4/6/8초 | ~4-7초 (프레임 수 기반) |

**중요**: Wan2.2는 오디오를 생성하지 않으므로, ComfyUI 프로바이더 사용 시 `add-audio.py`에서 TTS/BGM 추가가 **필수**다.

### 8.3 480p → 720p 업스케일 (선택)

5B 모델의 480p 출력이 품질 부족 시, FFmpeg로 간단 업스케일:

```bash
ffmpeg -i input_480p.mp4 -vf "scale=720:1280:flags=lanczos" -c:a copy output_720p.mp4
```

이 처리는 Phase 2에서 필요 시 `add-audio.py` 파이프라인에 추가한다.

---

## 9. Telegram UX

### 9.1 대기 시간 안내

ComfyUI 영상 생성은 Veo보다 느릴 수 있다. 사용자에게 예상 시간을 사전 안내:

```
🎬 쇼츠 영상 생성을 시작합니다!

📋 제작 계획:
  - 스타일: cinematic
  - 프로바이더: ComfyUI (Wan2.2)
  - 예상 클립: 7개
  - 예상 소요: 약 20-35분

⏳ 진행 상황을 실시간으로 알려드릴게요.
```

### 9.2 진행 상태 업데이트

```
[1/5] 📋 Continuity Table 생성 완료
[2/5] 📝 Beat Sheet 생성 완료
[3/5] 🎬 Shot List 생성 완료 (7 shots)
[4/5] 🎥 클립 생성 중...
  ✅ Shot 1/7 완료 (4s, I2V)
  🖼️ Shot 2/7: 컷 이미지 생성 중...
  ⏳ Shot 2/7: 비디오 렌더링 중... (45s)
  ✅ Shot 2/7 완료 (5s, I2V)
  ...
  ✅ Shot 7/7 완료 (6s, T2V)
[5/5] 🔗 최종 조립 완료!

🎉 영상이 완성되었습니다! (56초, 12.3MB)
```

### 9.3 실패 처리

```
❌ Shot 3 생성 실패 (GPU timeout)
🔄 재시도 중... (1/3)
✅ Shot 3 재시도 성공

---

❌ Shot 5 생성 실패 (3회 재시도 후 포기)
⚠️ 6/7 클립으로 최종 조립합니다.
```

### 9.4 구현 방식

진행 상태는 기존 Gateway 메시지 프로토콜로 전달:

```python
# agentic_video.py에서 진행 상태를 stdout으로 출력
# → Claude Code CLI가 캡처 → Agent가 Telegram으로 전달

# 또는 AG-UI 이벤트로 직접 전달 (기존 인프라 활용)
print(json.dumps({
    "type": "progress",
    "step": "4/5",
    "message": "Shot 2/7: 비디오 렌더링 중... (45s)"
}))
```

---

## 10. QC / 재시도

### 10.1 기본 QC (Phase 1)

| 검증 항목 | 기준 | 실패 시 |
|-----------|------|---------|
| 파일 존재 | `os.path.exists()` | 재시도 |
| 파일 크기 | > 100KB | 재시도 |
| FFprobe 유효성 | exit code 0 | 재시도 |
| 비디오 길이 | 예상 ±1초 | 경고 후 사용 |
| 블랙 프레임 | 첫/끝 프레임 검사 | 재시도 |

```python
def validate_clip(clip_path: str, expected_duration: float) -> bool:
    """Validate generated video clip"""
    if not os.path.exists(clip_path):
        return False

    if os.path.getsize(clip_path) < 100 * 1024:  # 100KB
        return False

    # FFprobe 검증
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries",
             "format=duration", "-of", "csv=p=0", clip_path],
            capture_output=True, text=True, check=True
        )
        duration = float(result.stdout.strip())
        if abs(duration - expected_duration) > 1.0:
            print(f"⚠️ Duration mismatch: {duration:.1f}s vs expected {expected_duration:.1f}s")
        return True
    except (subprocess.CalledProcessError, ValueError):
        return False
```

### 10.2 재시도 로직

```python
MAX_RETRIES = 3

def generate_clip_with_retry(
    shot: Shot,
    output_path: str,
    provider: str,
    max_retries: int = MAX_RETRIES
) -> Optional[str]:
    """Generate clip with automatic retry"""
    for attempt in range(max_retries):
        if attempt > 0:
            print(f"🔄 Retry {attempt}/{max_retries}...")
            # 재시도 시 seed 변경 (다른 결과 유도)
            time.sleep(5)

        result = generate_clip(shot, output_path, provider=provider)

        if result and validate_clip(result, shot.duration):
            return result

        print(f"❌ Attempt {attempt + 1} failed")

    print(f"❌ Shot {shot.id}: all {max_retries} attempts failed")
    return None
```

### 10.3 OOM 대응 (Phase 2)

| 실패 | 자동 대응 |
|------|----------|
| **OOM (GPU 메모리 부족)** | 해상도↓ (720p → 480p) → 프레임↓ (121 → 97) |
| **블랙 스크린** | seed 변경 → 재시도 |
| **모션 붕괴** | CFG↓ (3.5 → 3.0) → 카메라 모션 단순화 |
| **타임아웃** | shot 길이 축소 (7s → 5s) |

---

## 11. 비용 비교

### 11.1 프로바이더별 단가 비교

#### 클립당 비용 (6초 기준)

| 항목 | Veo 3.1 | Sora 2 | ComfyUI 5B (FLUX) | ComfyUI 5B (Gemini) | ComfyUI 14B (Gemini) |
|------|---------|--------|-------------------|--------------------|--------------------|
| 컷 이미지 | — | — | $0.003 (FLUX.2 ~1-2초) | $0.02 (Imagen 4 Fast) | $0.02 (Imagen 4 Fast) |
| 영상 렌더링 | **$2.40** | **$1.60** | **$0.05** (4090, ~2분) | **$0.05** | **$0.15** (4090, ~5분) |
| TTS | 포함 | $0.01 | $0.01 | $0.01 | $0.01 |
| **클립 합계** | **~$2.40** | **~$1.61** | **~$0.065** | **~$0.08** | **~$0.18** |

> Veo 비용: $0.40/초 × 6초 = $2.40
> ComfyUI GPU 비용: RTX 4090 $0.35/hr × (렌더링 시간)
> 5B ~2분/클립 = $0.35 × 2/60 ≈ $0.012 + 대기/오버헤드 포함 ~$0.05
> 14B ~5분/클립 = $0.35 × 5/60 ≈ $0.029 + 대기/오버헤드 포함 ~$0.15
> Imagen 4 Fast 이미지: ~$0.02/장 (Google Imagen 4 Fast API 기준)

#### Shorts 1편당 비용 (60초, 8클립)

| 프로바이더 | 클립 비용 | 후처리 | FFmpeg | **총 비용** |
|-----------|----------|--------|--------|-----------|
| **Veo 3.1** | $19.20 | 포함 | $0 | **~$19.20** |
| **Sora 2** | $12.88 | $0.08 | $0 | **~$12.96** |
| **ComfyUI 5B + FLUX** | $0.52 | $0.08 | $0 | **~$0.60** |
| **ComfyUI 5B + Gemini** | $0.64 | $0.08 | $0 | **~$0.72** |
| **ComfyUI 14B + Gemini** | $1.44 | $0.08 | $0 | **~$1.52** |

#### 월간 비용 (주 5편, 월 20편)

| 프로바이더 | 월 비용 | 연 비용 |
|-----------|--------|--------|
| **Veo 3.1** | **$384** | **$4,608** |
| **Sora 2** | **$259** | **$3,110** |
| **ComfyUI 5B + FLUX** | **$12** | **$144** |
| **ComfyUI 5B + Gemini** | **$14.4** | **$173** |
| **ComfyUI 14B + Gemini** | **$30.4** | **$365** |

### 11.2 품질 vs 비용 트레이드오프

| 비교 항목 | Veo 3.1 | ComfyUI 14B | ComfyUI 5B |
|-----------|---------|-------------|------------|
| 영상 품질 | ★★★★★ | ★★★★☆ | ★★★☆☆ |
| 내장 오디오 | ★★★★★ | ☆☆☆☆☆ | ☆☆☆☆☆ |
| 생성 속도 | ★★★★☆ (~2분) | ★★★☆☆ (~5분) | ★★★★☆ (~2분) |
| 비용 효율 | ★☆☆☆☆ | ★★★★☆ | ★★★★★ |
| 캐릭터 일관성 | ★★★☆☆ | ★★★★☆ (I2V) | ★★★☆☆ |

**권장 전략**:
- **기본값: ComfyUI 14B + Gemini** (고화질 I2V + 고품질 컷, $1.52/편) ← 기본 설정
- 비용 최적: **ComfyUI 5B + FLUX** (GPU 내부 처리, $0.60/편)
- 품질/속도 균형: **ComfyUI 5B + Gemini** (고품질 컷 이미지, GPU 부담↓, $0.72/편)
- 특별 편: **Veo 3.1** (최고 품질 + 네이티브 오디오, $19.20/편)

---

## 12. 보안

### 12.1 API 키 관리

| 키 | 저장 위치 | 접근 |
|----|-----------|------|
| `VAST_API_KEY` | `.env` (로컬) | comfyui_client.py |
| `GOOGLE_API_KEY` | `.env` (로컬) | Imagen 4 Fast 이미지 생성 (CUT_IMAGE_PROVIDER=gemini 시) |
| `HF_TOKEN` | `.env` (로컬) | Gated 모델 다운로드 시 |

### 12.2 인스턴스 보안 (On-Demand)

- Vast.ai 인스턴스는 공유 하드웨어에서 실행됨
- **민감 데이터 전송 금지**: 프롬프트와 이미지만 전송
- **인스턴스 파괴**: 작업 완료 후 즉시 `destroy_instance()` 호출
- **SSH 키**: 필요 시에만 등록, 작업 후 삭제

### 12.3 `.env` 템플릿 추가

```bash
# ComfyUI / Vast.ai 설정
VAST_API_KEY=                      # Vast.ai API 키
COMFYUI_MODEL=wan22-i2v-a14b        # wan22-i2v-a14b (기본, 고품질) | wan22-ti2v-5b (저비용)
COMFYUI_STEPS=20                   # 렌더링 스텝 수
COMFYUI_CFG=3.5                    # CFG 스케일
COMFYUI_RESOLUTION=720x1280        # 해상도 WxH (9:16 세로형, 14B 기본)
COMFYUI_FRAMES=121                 # 프레임 수
VIDEO_PROVIDER=comfyui             # 기본 프로바이더

# 컷 이미지 생성 프로바이더
CUT_IMAGE_PROVIDER=gemini          # gemini (Imagen 4 Fast, 기본) | flux (ComfyUI 내부)
GOOGLE_API_KEY=                    # Google API 키 — Imagen 4 Fast (CUT_IMAGE_PROVIDER=gemini 사용 시 필수)
```

---

## 13. 구축 로드맵

### Phase 1: 기본 ComfyUI 통합 (2주)

| 작업 | 예상 시간 | 설명 |
|------|-----------|------|
| `comfyui_client.py` 작성 | 2일 | Vast.ai Serverless 클라이언트 |
| 워크플로우 JSON 작성 | 1일 | TI2V-5B, I2V-A14B, FLUX.2 Klein 4B |
| `generate-video.py` 확장 | 1일 | comfyui 프로바이더 추가 |
| `agentic_video.py` 확장 | 0.5일 | Shot 확장, provider 전달 |
| SKILL.md 업데이트 | 0.5일 | 프로바이더 문서화 |
| Vast.ai 계정 설정 | 0.5일 | API 키, 엔드포인트 확인 |
| 단위 테스트 | 1일 | 각 함수별 테스트 |
| E2E 테스트 | 1일 | 전체 파이프라인 실행 |
| QC + 재시도 로직 | 1일 | 기본 검증 + 재시도 |
| Telegram UX | 0.5일 | 진행 상태 메시지 |
| **합계** | **~9일** | |

### Phase 2: On-Demand + 고급 기능 (2주)

| 작업 | 설명 |
|------|------|
| `VastOnDemandManager` 구현 | 인스턴스 생명주기 관리 |
| OOM 자동 대응 | 해상도/프레임 다운그레이드 |
| 480p → 720p 업스케일 | FFmpeg lanczos 또는 Real-ESRGAN |
| FLF2V 워크플로우 | First-Last Frame 트랜지션 |
| **LTX-2 프로바이더 추가** | **19B, 45-90초, 4K@50fps, 오디오 싱크** (Wan2.2 대안) |
| 비용 추적 | GPU 사용 시간 로깅 |

### Phase 3: 최적화 (2주)

| 작업 | 설명 |
|------|------|
| TeaCache 가속 | ~30% 속도 향상 |
| Lightning LoRA | ~80% 속도 향상 (품질 약간 하락) |
| VACE R2V | 캐릭터 일관성 향상 |
| 배치 처리 | 여러 편 연속 생산 최적화 |
| 자동 스케줄링 | 매일 자동 Shorts 제작 |

---

## 14. 체크리스트

### Phase 1 실행 체크리스트

- [ ] **환경 설정**
  - [ ] Vast.ai 계정 생성 + API 키 발급
  - [ ] `.env`에 `VAST_API_KEY` 추가
  - [ ] Vast.ai Serverless ComfyUI 엔드포인트 확인
  - [ ] `.env`에 `GOOGLE_API_KEY` 추가 (Imagen 4 Fast 이미지 생성 사용 시)
  - [ ] `.env`에 `CUT_IMAGE_PROVIDER` 설정 (flux 또는 gemini)

- [ ] **워크플로우 준비**
  - [ ] `workflows/` 디렉토리 생성
  - [ ] `wan22_ti2v_5b.json` 작성 및 테스트
  - [ ] `wan22_i2v_a14b.json` 작성 및 테스트
  - [ ] `flux2_klein_4b.json` 작성 및 테스트
  - [ ] 각 워크플로우 로컬 ComfyUI에서 수동 검증

- [ ] **코드 구현**
  - [ ] `comfyui_client.py` 작성
    - [ ] `ComfyUIClient.__init__()` (API 키 로드)
    - [ ] `generate_video()` (Serverless 호출)
    - [ ] `generate_image()` (FLUX.2 Klein 4B 이미지 생성)
    - [ ] `generate_image_gemini()` (Imagen 4 Fast 이미지 생성)
    - [ ] `generate_cut_image()` (프로바이더 라우터)
    - [ ] `upload_image_to_comfyui()` (Imagen 4 Fast 이미지 → ComfyUI 업로드)
    - [ ] `download_result()` (ComfyUI /view → 로컬 다운로드)
    - [ ] `_build_video_workflow()` (JSON 파라미터화)
    - [ ] `_build_image_workflow()` (FLUX.2 워크플로우)
  - [ ] `generate-video.py` 수정
    - [ ] Configuration 추가 (L32 부근)
    - [ ] `generate_video_comfyui()` 함수 추가
    - [ ] `generate_video()` router에 comfyui 분기 추가
    - [ ] CLI `--provider` choices에 comfyui 추가
  - [ ] `agentic_video.py` 수정
    - [ ] Shot 데이터클래스에 `rendering_hint`, `reference_image` 추가
    - [ ] CLI `--provider` choices에 comfyui 추가
  - [ ] SKILL.md 업데이트

- [ ] **QC / 재시도**
  - [ ] `validate_clip()` 구현
  - [ ] `generate_clip_with_retry()` 구현

- [ ] **테스트**
  - [ ] FLUX.2 Klein 4B 이미지 생성 테스트
  - [ ] Imagen 4 Fast 이미지 생성 테스트
  - [ ] TI2V-5B T2V 워크플로우 테스트
  - [ ] TI2V-5B I2V 워크플로우 테스트 (FLUX.2 → I2V 파이프라인)
  - [ ] I2V-A14B 2-Pass 워크플로우 테스트
  - [ ] 전체 파이프라인 E2E: `agentic_video.py --provider comfyui --brief "test"`
  - [ ] Telegram에서 "쇼츠 만들어줘" 실행 확인
  - [ ] 비용 검증: 실제 Vast.ai 과금 확인

- [ ] **문서화**
  - [ ] SKILL.md에 ComfyUI 프로바이더 설명 추가
  - [ ] `.env.example` 업데이트
  - [ ] 이 문서(SYS-003) 최종 업데이트

---

## 15. 부록

### A. 모델 비교 상세

| 항목 | Wan2.2-TI2V-5B | Wan2.2-I2V-A14B | LTX-2 (Phase 2) | Veo 3.1 |
|------|----------------|-----------------|------------------|---------|
| 파라미터 | 5B | 14B (MoE) | 19B | 비공개 |
| 아키텍처 | Single DiT | MoE DiT (2-Expert) | DiT + Audio | 비공개 |
| 입력 | Text + Image(선택) | Image 필수 | Text + Image | Text |
| 최대 해상도 | 832×480 | 1280×720 | 4K@50fps | 1080p |
| 최대 길이 | 169프레임 (~7s) | 169프레임 (~7s) | **45-90초** | 8s |
| VRAM | ~8GB | ~24GB | ~40GB | 클라우드 |
| 생성 시간 (RTX 4090) | ~1-2분 | ~3-5분 | TBD | ~2분 |
| 오디오 | 없음 | 없음 | **네이티브 싱크** | 있음 |
| 라이선스 | Apache 2.0 | Apache 2.0 | Apache 2.0 | 상용 API |

> **LTX-2**: 2026.01 출시. 45-90초 장편 비디오, 4K@50fps, 오디오 네이티브 싱크 지원.
> Phase 2에서 Wan2.2 대안으로 통합 예정. ~40GB VRAM 필요 (A100 권장).

### B. 유효 프레임 수 (Wan2.2)

Wan2.2는 **(4k+1)** 프레임만 지원:

| k | 프레임 수 | @24fps 길이 | @30fps 길이 |
|---|----------|------------|------------|
| 24 | 97 | 4.04s | 3.23s |
| 30 | 121 | 5.04s | 4.03s |
| 36 | 145 | 6.04s | 4.83s |
| 42 | 169 | 7.04s | 5.63s |

### C. 용어집

| 용어 | 설명 |
|------|------|
| **I2V** | Image-to-Video. 이미지를 기반으로 영상 생성 |
| **T2V** | Text-to-Video. 텍스트 프롬프트로 영상 생성 |
| **TI2V** | Text+Image-to-Video. 텍스트와 이미지 모두 사용 |
| **MoE** | Mixture of Experts. 다중 전문가 모델 아키텍처 |
| **2-Pass** | 14B 모델의 High-Noise/Low-Noise 2단계 생성 |
| **FLF2V** | First-Last Frame to Video. 처음/끝 프레임 조건 생성 |
| **VACE R2V** | Reference-to-Video. 참조 이미지 기반 캐릭터 일관성 |
| **CFG** | Classifier-Free Guidance. 프롬프트 준수도 조절 |
| **Klein 4B** | FLUX.2의 경량 모델 (4B 파라미터, 4스텝, ~9GB VRAM, Apache 2.0) |
| **Imagen 4 Fast** | Google Imagen 4 고속 모델 ($0.02/장, ~2초) |
| **LTX-2** | Lightricks 19B 비디오 모델 (45-90초, 4K, 오디오 싱크, Phase 2) |
| **ComfyUI** | 노드 기반 AI 이미지/영상 생성 UI |
| **PyWorker** | Vast.ai Serverless의 HTTP 프록시 워커 |
| **xfade** | FFmpeg의 크로스페이드 전환 필터 |

### D. 관련 파일 경로

```
scripts/youtube-shorts/
  ├── generate-video.py           # 영상 생성 API (L428: 프로바이더 router)
  ├── agentic_video.py            # 파이프라인 오케스트레이터 (L37: Shot, L441: run_pipeline)
  ├── add-audio.py                # TTS + 오디오 믹싱
  ├── upload-youtube.py           # YouTube 업로드
  ├── comfyui_client.py           # [신규] ComfyUI 클라이언트
  └── workflows/                  # [신규] ComfyUI 워크플로우 JSON
      ├── wan22_ti2v_5b.json
      ├── wan22_i2v_a14b.json
      └── flux2_klein_4b.json

.claude/skills/youtube-shorts/
  └── SKILL.md                    # 스킬 정의 (프로바이더 목록)

docs/video-generation/
  ├── SHORTS-AUTO-SYS-002.md      # 이전 버전 (참조 아키텍처)
  └── SHORTS-COMFYUI-SYS-003.md   # 본 문서
```
