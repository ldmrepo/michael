#!/usr/bin/env python3
"""
Video Generation API - Veo 3.1 & Sora 2 & ComfyUI 지원

Google Veo, OpenAI Sora, 또는 ComfyUI (Direct Instance / Vast.ai Serverless + Wan2.2)를 사용하여 영상을 생성합니다.

Usage:
    # Veo 사용 (기본값)
    python3 generate-video.py --prompt "A cat walking" --provider veo

    # Sora 사용
    python3 generate-video.py --prompt "A cat walking" --provider sora

    # ComfyUI 사용 (Direct Instance — SSH 터널)
    COMFYUI_HOST=http://localhost:8188 python3 generate-video.py --prompt "A cat walking" --provider comfyui

    # ComfyUI 사용 (Vast.ai Serverless)
    python3 generate-video.py --prompt "A cat walking" --provider comfyui

    # 환경변수로 선택
    VIDEO_PROVIDER=comfyui python3 generate-video.py --prompt "A cat walking"
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error
import subprocess
from typing import Optional

# S3 Storage — optional
try:
    from s3_storage import S3Storage
    HAS_S3 = True
except ImportError:
    HAS_S3 = False


# =============================================================================
# Configuration
# =============================================================================

# 기본 프로바이더 (환경변수로 오버라이드 가능)
DEFAULT_PROVIDER = os.environ.get("VIDEO_PROVIDER", "veo")

# Veo 설정
VEO_PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "gen-lang-client-0072871637")
VEO_LOCATION = "us-central1"
VEO_MODEL = os.environ.get("VEO_MODEL", "veo-3.1-generate-preview")
VEO_VALID_DURATIONS = [4, 6, 8]

# Sora 설정
SORA_API_KEY = os.environ.get("OPENAI_API_KEY", "")
SORA_MODEL = os.environ.get("SORA_MODEL", "sora-2")
SORA_VALID_DURATIONS = [4, 8, 12]  # Sora 2 지원 길이

# ComfyUI 설정 (Direct Instance / Vast.ai Serverless)
COMFYUI_HOST = os.environ.get("COMFYUI_HOST", "")  # Direct: http://localhost:8188 | 빈 값: Serverless
COMFYUI_MODEL = os.environ.get("COMFYUI_MODEL", "wan22-i2v-a14b")  # wan22-i2v-a14b | wan22-ti2v-5b
COMFYUI_STEPS = int(os.environ.get("COMFYUI_STEPS", "20"))
COMFYUI_CFG = float(os.environ.get("COMFYUI_CFG", "3.5"))
COMFYUI_RESOLUTION = os.environ.get("COMFYUI_RESOLUTION", "720x1280")  # WxH (9:16 세로형)
COMFYUI_FRAMES = int(os.environ.get("COMFYUI_FRAMES", "121"))  # 121 frames ≈ 5s @24fps
COMFYUI_LIGHTNING = os.environ.get("COMFYUI_LIGHTNING", "").lower() in ("1", "true", "yes")  # Lightning LoRA (4-step)

# 컷 이미지 생성 프로바이더
CUT_IMAGE_PROVIDER = os.environ.get("CUT_IMAGE_PROVIDER", "gemini")  # gemini | flux
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")


# =============================================================================
# Veo (Google Vertex AI)
# =============================================================================

def get_gcp_access_token() -> str:
    """Get GCP access token using gcloud CLI."""
    gcloud_paths = [
        "gcloud",
        os.path.expanduser("~/work/workspace/ai_agentic/opencode-demo/michael/google-cloud-sdk/bin/gcloud"),
        "/Users/ldm/work/workspace/ai_agentic/opencode-demo/michael/google-cloud-sdk/bin/gcloud",
    ]

    for gcloud_path in gcloud_paths:
        try:
            result = subprocess.run(
                [gcloud_path, "auth", "print-access-token"],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue

    raise RuntimeError("gcloud CLI not found or not authenticated. Run: gcloud auth login")


def generate_video_veo(
    prompt: str,
    duration: int = 8,
    output_path: str = "/tmp/shorts/video.mp4",
    aspect_ratio: str = "9:16",
) -> Optional[str]:
    """Generate video using Google Veo API.

    Args:
        prompt: Text prompt describing the video
        duration: Video duration in seconds
        output_path: Path to save the generated video
        aspect_ratio: Video aspect ratio (9:16 for shorts)

    Returns:
        Output path if successful, None otherwise
    """
    access_token = get_gcp_access_token()

    endpoint = (
        f"https://{VEO_LOCATION}-aiplatform.googleapis.com/v1/"
        f"projects/{VEO_PROJECT_ID}/locations/{VEO_LOCATION}/"
        f"publishers/google/models/{VEO_MODEL}:predictLongRunning"
    )

    # Round to nearest valid duration
    video_duration = min(VEO_VALID_DURATIONS, key=lambda x: abs(x - min(duration, 8)))

    request_body = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "aspectRatio": aspect_ratio,
            "personGeneration": "allow_adult",
            "sampleCount": 1,
            "includeAudio": True,
            "durationSeconds": video_duration,
        }
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    print(f"🎬 Generating video with Veo 3.1...")
    print(f"   Model: {VEO_MODEL}")
    print(f"   Prompt: {prompt[:80]}...")
    print(f"   Duration: {video_duration}s")
    print(f"   Aspect ratio: {aspect_ratio}")

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(request_body).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"❌ Veo API Error: {e.code}")
        print(f"   Details: {error_body[:300]}")
        return None

    # Handle long-running operation
    if "name" in data:
        operation_name = data["name"]
        print(f"📋 Operation started: {operation_name.split('/')[-1]}")

        video_data = poll_veo_operation(operation_name, access_token)
        if video_data:
            return save_video_data(video_data, output_path, access_token)

    # Direct response
    if "predictions" in data:
        video_data = data["predictions"][0]
        return save_video_data(video_data, output_path, access_token)

    print("❌ Failed to generate video with Veo")
    return None


def poll_veo_operation(operation_name: str, access_token: str, max_wait: int = 600) -> Optional[dict]:
    """Poll Veo long-running operation until completion."""
    parts = operation_name.split("/operations/")
    model_path = parts[0]
    endpoint = f"https://{VEO_LOCATION}-aiplatform.googleapis.com/v1/{model_path}:fetchPredictOperation"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    request_body = {"operationName": operation_name}

    start_time = time.time()
    while time.time() - start_time < max_wait:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(request_body).encode("utf-8"),
            headers=headers,
            method="POST"
        )

        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            print(f"   Poll error: {e.code}")
            time.sleep(10)
            continue

        if data.get("done"):
            if "error" in data:
                print(f"❌ Operation failed: {data['error']}")
                return None

            if "response" in data:
                resp = data["response"]
                if "videos" in resp:
                    return resp["videos"][0]
                elif "predictions" in resp:
                    return resp["predictions"][0]
                elif "generatedSamples" in resp:
                    return resp["generatedSamples"][0]["video"]

            return None

        elapsed = int(time.time() - start_time)
        print(f"⏳ Generating... ({elapsed}s)")
        time.sleep(15)

    print(f"❌ Timeout after {max_wait}s")
    return None


# =============================================================================
# Sora (OpenAI)
# =============================================================================

def generate_video_sora(
    prompt: str,
    duration: int = 8,
    output_path: str = "/tmp/shorts/video.mp4",
    aspect_ratio: str = "9:16",
) -> Optional[str]:
    """Generate video using OpenAI Sora API.

    Args:
        prompt: Text prompt describing the video
        duration: Video duration in seconds
        output_path: Path to save the generated video
        aspect_ratio: Video aspect ratio (9:16 for shorts)

    Returns:
        Output path if successful, None otherwise
    """
    if not SORA_API_KEY:
        print("❌ OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        print("   export OPENAI_API_KEY='sk-...'")
        return None

    # Convert aspect ratio to Sora format (width x height)
    # Sora supports: 720x1280 (9:16), 1280x720 (16:9), 1024x1024 (1:1)
    if aspect_ratio == "9:16":
        resolution = "720x1280"
    elif aspect_ratio == "16:9":
        resolution = "1280x720"
    else:
        resolution = "1024x1024"

    # Round to nearest valid duration (4, 8, 12)
    video_duration = min(SORA_VALID_DURATIONS, key=lambda x: abs(x - min(duration, 12)))

    # OpenAI Sora API endpoint
    endpoint = "https://api.openai.com/v1/videos"

    request_body = {
        "model": SORA_MODEL,
        "prompt": prompt,
        "size": resolution,
        "seconds": str(video_duration),  # API expects string: "4", "8", or "12"
    }

    headers = {
        "Authorization": f"Bearer {SORA_API_KEY}",
        "Content-Type": "application/json",
    }

    print(f"🎬 Generating video with Sora...")
    print(f"   Model: {SORA_MODEL}")
    print(f"   Prompt: {prompt[:80]}...")
    print(f"   Duration: {video_duration}s")
    print(f"   Resolution: {resolution}")

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(request_body).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"❌ Sora API Error: {e.code}")
        print(f"   Details: {error_body[:500]}")
        return None
    except urllib.error.URLError as e:
        print(f"❌ Network Error: {e.reason}")
        return None

    # Sora returns a job object with id and status
    if "id" in data:
        job_id = data["id"]
        status = data.get("status", "unknown")
        print(f"📋 Job started: {job_id} (status: {status})")
        return poll_sora_job(job_id, output_path)

    print("❌ Failed to generate video with Sora")
    print(f"   Response: {json.dumps(data, indent=2)[:500]}")
    return None


def poll_sora_job(job_id: str, output_path: str, max_wait: int = 600) -> Optional[str]:
    """Poll Sora async job until completion."""
    status_endpoint = f"https://api.openai.com/v1/videos/{job_id}"

    headers = {
        "Authorization": f"Bearer {SORA_API_KEY}",
    }

    start_time = time.time()
    while time.time() - start_time < max_wait:
        req = urllib.request.Request(status_endpoint, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            print(f"   Poll error: {e.code} - {error_body[:200]}")
            time.sleep(10)
            continue

        status = data.get("status", "")

        if status == "completed":
            # Download the video content
            video_endpoint = f"https://api.openai.com/v1/videos/{job_id}/content"
            return download_sora_video(video_endpoint, output_path, headers)

        if status in ("failed", "cancelled"):
            failure_reason = data.get("failure_reason", "Unknown error")
            print(f"❌ Job {status}: {failure_reason}")
            return None

        elapsed = int(time.time() - start_time)
        progress = data.get("progress", 0)
        print(f"⏳ Generating... ({elapsed}s, status: {status}, progress: {progress}%)")
        time.sleep(10)

    print(f"❌ Timeout after {max_wait}s")
    return None


def download_sora_video(video_endpoint: str, output_path: str, headers: dict) -> Optional[str]:
    """Download video from Sora content endpoint."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    print(f"📥 Downloading video...")
    req = urllib.request.Request(video_endpoint, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req) as response:
            with open(output_path, "wb") as f:
                f.write(response.read())

        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"✅ Video saved: {output_path} ({size_mb:.2f} MB)")
        return output_path
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"❌ Download error: {e.code} - {error_body[:200]}")
        return None


# =============================================================================
# Common Utilities
# =============================================================================

def save_video_data(video_data: dict, output_path: str, access_token: Optional[str] = None) -> Optional[str]:
    """Save video data (base64 or URI) to file."""
    if "bytesBase64Encoded" in video_data:
        return save_base64_video(video_data["bytesBase64Encoded"], output_path)
    elif "gcsUri" in video_data:
        return download_video_from_gcs(video_data["gcsUri"], output_path)
    elif "url" in video_data:
        return download_video_from_url(video_data["url"], output_path)
    return None


def save_base64_video(base64_data: str, output_path: str) -> str:
    """Save base64 encoded video to file."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    print(f"📥 Saving video to {output_path}...")
    video_bytes = base64.b64decode(base64_data)

    with open(output_path, "wb") as f:
        f.write(video_bytes)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"✅ Video saved: {output_path} ({size_mb:.2f} MB)")
    return output_path


def download_video_from_url(url: str, output_path: str) -> str:
    """Download video from HTTP URL."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    print(f"📥 Downloading video...")
    req = urllib.request.Request(url)

    with urllib.request.urlopen(req) as response:
        with open(output_path, "wb") as f:
            f.write(response.read())

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"✅ Video saved: {output_path} ({size_mb:.2f} MB)")
    return output_path


def download_video_from_gcs(gcs_uri: str, output_path: str) -> str:
    """Download video from Google Cloud Storage."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    print(f"📥 Downloading from GCS...")
    subprocess.run(["gsutil", "cp", gcs_uri, output_path], check=True)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"✅ Video saved: {output_path} ({size_mb:.2f} MB)")
    return output_path


# =============================================================================
# ComfyUI (Vast.ai + Wan2.2)
# =============================================================================

def generate_video_comfyui(
    prompt: str,
    duration: int = 8,
    output_path: str = "/tmp/shorts/video.mp4",
    aspect_ratio: str = "9:16",
    input_image: Optional[str] = None,
    lightning: bool = False,
) -> Optional[str]:
    """Generate video using ComfyUI via Direct Instance or Vast.ai Serverless.

    When S3 is available, creates a job and uploads all assets:
      s3://bucket/jobs/{job_id}/plan.json
      s3://bucket/jobs/{job_id}/input_image.png
      s3://bucket/jobs/{job_id}/clip_01.mp4

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

    # Initialize S3 job tracking
    job_id = None
    s3 = client.s3
    if s3 and HAS_S3:
        job_id = s3.generate_job_id()
        print(f"📦 S3 Job: {job_id}")

    # Step 1: I2V mode — generate cut image if needed
    if input_image is None and COMFYUI_MODEL != "wan22-ti2v-5b":
        provider_name = "Imagen 4" if CUT_IMAGE_PROVIDER == "gemini" else "FLUX.2 Klein"
        print(f"🖼️ Generating cut image with {provider_name}...")
        input_image = client.generate_cut_image(prompt, 480, 832, job_id=job_id)
        if input_image is None:
            print("⚠️ Image generation failed, falling back to T2V")

    # Step 2: Calculate frame count
    fps = 24
    frames = min(duration * fps, 169)  # Max 169 frames for Wan2.2
    # Wan2.2 requires (4k+1) frames: 97, 121, 145, 169
    valid_frames = [97, 121, 145, 169]
    frames = min(valid_frames, key=lambda x: abs(x - frames))

    # Step 3: Determine resolution
    if aspect_ratio == "9:16":
        width, height = (480, 832) if "5b" in COMFYUI_MODEL else (720, 1280)
    elif aspect_ratio == "16:9":
        width, height = (832, 480) if "5b" in COMFYUI_MODEL else (1280, 720)
    else:
        width, height = (640, 640) if "5b" in COMFYUI_MODEL else (960, 960)

    # Step 4: Upload job metadata to S3
    if s3 and job_id:
        metadata = {
            "job_id": job_id,
            "prompt": prompt,
            "model": COMFYUI_MODEL,
            "resolution": f"{width}x{height}",
            "frames": frames,
            "fps": fps,
            "duration_s": frames / fps,
            "steps": COMFYUI_STEPS,
            "cfg": COMFYUI_CFG,
            "aspect_ratio": aspect_ratio,
            "mode": "I2V" if input_image else "T2V",
            "cut_image_provider": CUT_IMAGE_PROVIDER,
        }
        try:
            s3.upload_job_metadata(job_id, metadata)
        except Exception as e:
            print(f"⚠️ Failed to upload job metadata: {e}")

    # Step 5: Execute ComfyUI workflow
    lightning = lightning or COMFYUI_LIGHTNING
    steps = 4 if lightning else COMFYUI_STEPS
    print(f"🎬 Generating video with ComfyUI (Wan2.2)...")
    print(f"   Model: {COMFYUI_MODEL}")
    print(f"   Resolution: {width}x{height}")
    print(f"   Frames: {frames} ({frames/fps:.1f}s @{fps}fps)")
    print(f"   Steps: {steps}{' (Lightning LoRA)' if lightning else ''}")
    print(f"   Mode: {'I2V' if input_image else 'T2V'}")

    result = client.generate_video(
        prompt=prompt,
        width=width,
        height=height,
        frames=frames,
        steps=steps,
        cfg=COMFYUI_CFG,
        model=COMFYUI_MODEL,
        input_image=input_image,
        lightning=lightning,
    )

    if result:
        client.download_result(result, output_path, job_id=job_id, clip_name="clip_01.mp4")
        print(f"✅ Video saved: {output_path}")
        if job_id and s3:
            print(f"   S3 Job: s3://{s3.bucket}/jobs/{job_id}/")
        return output_path

    print("❌ ComfyUI video generation failed")
    return None


# =============================================================================
# Main Entry Point
# =============================================================================

def generate_video(
    prompt: str,
    duration: int = 8,
    output_path: str = "/tmp/shorts/video.mp4",
    aspect_ratio: str = "9:16",
    provider: Optional[str] = None,
    lightning: bool = False,
) -> Optional[str]:
    """Generate video using specified provider.

    Args:
        prompt: Text prompt describing the video
        duration: Video duration in seconds
        output_path: Path to save the generated video
        aspect_ratio: Video aspect ratio (9:16 for shorts)
        provider: 'veo', 'sora', or 'comfyui' (default from VIDEO_PROVIDER env)
        lightning: Use Lightning LoRA for fast 4-step inference (ComfyUI only)

    Returns:
        Output path if successful, None otherwise
    """
    provider = provider or DEFAULT_PROVIDER

    if provider.lower() == "sora":
        return generate_video_sora(prompt, duration, output_path, aspect_ratio)
    elif provider.lower() == "comfyui":
        return generate_video_comfyui(prompt, duration, output_path, aspect_ratio, lightning=lightning)
    else:
        return generate_video_veo(prompt, duration, output_path, aspect_ratio)


def main():
    parser = argparse.ArgumentParser(
        description="Generate video using Veo, Sora, or ComfyUI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Veo (기본값)
  python3 generate-video.py -p "A sunset over ocean" -o video.mp4

  # Sora
  python3 generate-video.py -p "A cat playing" --provider sora

  # ComfyUI (Vast.ai + Wan2.2)
  python3 generate-video.py -p "A sunset" --provider comfyui -d 5

  # 환경변수로 선택
  VIDEO_PROVIDER=comfyui python3 generate-video.py -p "A cat"

Environment Variables:
  VIDEO_PROVIDER        기본 프로바이더 (veo/sora/comfyui)
  VEO_MODEL             Veo 모델 (veo-3.1-generate-preview)
  SORA_MODEL            Sora 모델 (sora)
  OPENAI_API_KEY        Sora 사용 시 필수
  GOOGLE_CLOUD_PROJECT  Veo GCP 프로젝트 ID
  COMFYUI_HOST          Direct Instance URL (e.g. http://localhost:8188)
  VAST_API_KEY          Serverless 모드 시 필요 (Vast.ai)
  COMFYUI_MODEL         wan22-i2v-a14b (기본) | wan22-ti2v-5b
  CUT_IMAGE_PROVIDER    gemini (기본) | flux
  GOOGLE_API_KEY        Imagen 4 Fast 사용 시 필수
"""
    )

    parser.add_argument("--prompt", "-p", required=True, help="Video generation prompt")
    parser.add_argument("--duration", "-d", type=int, default=8, help="Duration in seconds")
    parser.add_argument("--output", "-o", default="/tmp/shorts/video.mp4", help="Output path")
    parser.add_argument("--aspect-ratio", "-a", default="9:16",
                        choices=["9:16", "16:9", "1:1"],
                        help="Aspect ratio (default: 9:16 for shorts)")
    parser.add_argument("--provider", choices=["veo", "sora", "comfyui"],
                        default=DEFAULT_PROVIDER,
                        help=f"Video provider (default: {DEFAULT_PROVIDER})")
    parser.add_argument("--lightning", action="store_true",
                        help="Use Lightning LoRA for 4-step fast inference (ComfyUI only)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    print("=" * 50)
    print(f"🎥 Video Generator - {args.provider.upper()}")
    print("=" * 50)

    result = generate_video(
        prompt=args.prompt,
        duration=args.duration,
        output_path=args.output,
        aspect_ratio=args.aspect_ratio,
        provider=args.provider,
        lightning=args.lightning,
    )

    if args.json:
        output = {
            "success": result is not None,
            "provider": args.provider,
            "output_path": result,
            "duration": args.duration,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    elif result:
        print()
        print("=" * 50)
        print(f"🎉 Video generation complete!")
        print(f"   Provider: {args.provider.upper()}")
        print(f"   Path: {result}")
        print("=" * 50)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
