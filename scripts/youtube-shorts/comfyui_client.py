#!/usr/bin/env python3
"""
ComfyUI Client — Vast.ai Serverless + On-Demand ComfyUI integration.

Supports:
  - Wan2.2-TI2V-5B (Text+Image to Video, 5B, 480x832)
  - Wan2.2-I2V-A14B (Image to Video, 14B MoE 2-Pass, 720x1280)
  - FLUX.2 Klein 4B (Image generation, 4B, 4 steps)
  - Imagen 4 Fast (Image generation via Google API)

Usage:
    from comfyui_client import ComfyUIClient

    client = ComfyUIClient()
    result = client.generate_video(prompt="sunset", width=720, height=1280, frames=121)
    client.download_result(result, "/tmp/shorts/video.mp4")
"""

import asyncio
import base64
import json
import os
import random
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

# Vast.ai Serverless SDK (pip install vastai-sdk)
from vastai_sdk import Serverless

# =============================================================================
# Constants
# =============================================================================

WORKFLOW_DIR = Path(__file__).parent / "workflows"

# Cut image provider: "gemini" (Imagen 4 Fast) or "flux" (FLUX.2 Klein 4B)
CUT_IMAGE_PROVIDER = os.environ.get("CUT_IMAGE_PROVIDER", "gemini")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

# QC constants
MAX_RETRIES = 3


# =============================================================================
# Workflow Loading & Parameterization
# =============================================================================

def _load_workflow(name: str) -> dict:
    """Load workflow JSON template."""
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
    """Replace placeholders in workflow JSON."""
    wf = json.loads(json.dumps(workflow))  # Deep copy

    for node_id, node in wf.items():
        inputs = node.get("inputs", {})

        # Prompt substitution
        if node["class_type"] == "CLIPTextEncode":
            if "{{PROMPT}}" in inputs.get("text", ""):
                inputs["text"] = prompt

        # Seed substitution (random each time)
        for key in ("seed", "noise_seed"):
            if key in inputs:
                if inputs[key] == "__RANDOM_INT__" or seed:
                    inputs[key] = seed or random.randint(0, 2**53)

        # Resolution / frame count
        if node["class_type"] in ("EmptyHunyuanLatentVideo", "Wan2.2ImageToVideoLatent"):
            inputs["width"] = width
            inputs["height"] = height
            inputs["length"] = frames

        # Image input
        if node["class_type"] == "LoadImage" and input_image:
            inputs["image"] = input_image

        # Steps / CFG
        if node["class_type"] in ("KSampler", "KSamplerAdvanced"):
            inputs["steps"] = steps
            inputs["cfg"] = cfg
            # 2-Pass: auto-calculate split step
            if node["class_type"] == "KSamplerAdvanced":
                split = steps // 2
                meta_title = node.get("_meta", {}).get("title", "")
                if "Pass 1" in meta_title or "High Noise" in meta_title:
                    inputs["end_at_step"] = split
                elif "Pass 2" in meta_title or "Low Noise" in meta_title:
                    inputs["start_at_step"] = split

    return wf


# =============================================================================
# ComfyUIClient (Vast.ai Serverless)
# =============================================================================

class ComfyUIClient:
    """ComfyUI client via Vast.ai Serverless (Phase 1) or On-Demand (Phase 2)."""

    ENDPOINT_NAME = "comfyui-json"

    def __init__(self, comfyui_host: Optional[str] = None):
        self.api_key = os.environ.get("VAST_API_KEY")
        if not self.api_key:
            raise ValueError("VAST_API_KEY 환경변수가 필요합니다")
        # Serverless: None (SDK response contains URL)
        # On-Demand: "http://<ip>:<port>"
        self.comfyui_host = comfyui_host

    async def _submit_workflow(self, workflow: dict) -> dict:
        """Submit ComfyUI workflow to Vast.ai Serverless."""
        payload = {
            "input": {
                "workflow_json": workflow,
            }
        }
        async with Serverless(api_key=self.api_key) as client:
            endpoint = await client.get_endpoint(name=self.ENDPOINT_NAME)
            result = await endpoint.request(
                "/generate/sync",
                payload,
                cost=100,
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
        """Generate video via ComfyUI workflow."""
        workflow = self._build_video_workflow(
            prompt, width, height, frames, steps, cfg, model, input_image
        )
        try:
            result = asyncio.run(self._submit_workflow(workflow))
            return self._extract_output(result)
        except Exception as e:
            print(f"❌ Vast.ai error: {e}")
            return None

    def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "9:16",
        output_path: str = "/tmp/shorts/cut.png",
    ) -> Optional[str]:
        """Generate image via FLUX.2 Klein 4B workflow."""
        workflow = self._build_image_workflow(prompt, aspect_ratio)
        try:
            result = asyncio.run(self._submit_workflow(workflow))
            output = self._extract_output(result)
            if output and "images" in output:
                img = output["images"][0]
                url_or_filename = img.get("url") or img.get("filename")
                return self._download_output(url_or_filename, output_path)
            return None
        except Exception as e:
            print(f"❌ Image generation error: {e}")
            return None

    @staticmethod
    def _extract_output(result: dict) -> Optional[dict]:
        """Extract output from Vast.ai Serverless response.

        Vast.ai response format:
          {"status": "...", "output": [...], "comfyui_response": {...}, ...}
        """
        if not result:
            return None
        # Direct output from Serverless response
        if "output" in result:
            outputs = result["output"]
            if isinstance(outputs, list) and outputs:
                return outputs[0]
            return outputs
        # Fallback: raw response passthrough
        return result

    def generate_cut_image(
        self,
        prompt: str,
        width: int = 480,
        height: int = 832,
        output_path: str = "/tmp/shorts/cut.png",
    ) -> Optional[str]:
        """Generate cut image using configured provider."""
        provider = CUT_IMAGE_PROVIDER

        if provider == "flux":
            return self.generate_image(prompt, f"{width}:{height}", output_path)
        else:  # gemini (default)
            return generate_image_gemini(prompt, width, height, output_path)

    def download_result(self, result: dict, output_path: str) -> str:
        """Download result from ComfyUI output."""
        video = result.get("videos", [{}])[0] if "videos" in result else result
        url_or_filename = video.get("url") or video.get("filename")
        if not url_or_filename:
            raise ValueError("No output filename/url in result")
        return self._download_output(url_or_filename, output_path)

    def _download_output(self, filename_or_url: str, output_path: str) -> str:
        """Download file from ComfyUI output to local path."""
        if filename_or_url.startswith("http"):
            url = filename_or_url
        elif self.comfyui_host:
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

    def _build_video_workflow(
        self,
        prompt: str,
        width: int,
        height: int,
        frames: int,
        steps: int = 20,
        cfg: float = 3.5,
        model: str = "wan22-i2v-a14b",
        input_image: Optional[str] = None,
    ) -> dict:
        """Build parameterized video workflow."""
        if model == "wan22-ti2v-5b":
            wf = _load_workflow("wan22_ti2v_5b")
            # T2V mode: replace LoadImage + I2V latent with empty latent
            if not input_image:
                del wf["6"]  # Remove LoadImage
                wf["7"] = {
                    "class_type": "EmptyHunyuanLatentVideo",
                    "inputs": {
                        "width": width,
                        "height": height,
                        "length": frames,
                        "batch_size": 1,
                    },
                    "_meta": {"title": "Empty Latent (T2V)"},
                }
        else:
            wf = _load_workflow("wan22_i2v_a14b")

        return _parameterize_workflow(
            wf, prompt, width, height, frames, steps, cfg, input_image=input_image
        )

    def _build_image_workflow(self, prompt: str, aspect_ratio: str = "9:16") -> dict:
        """Build parameterized FLUX.2 Klein 4B image workflow."""
        wf = _load_workflow("flux2_klein_4b")

        # Parse aspect ratio for resolution
        if aspect_ratio in ("9:16", "480:832"):
            width, height = 480, 832
        elif aspect_ratio in ("16:9", "832:480"):
            width, height = 832, 480
        else:
            width, height = 640, 640

        # Update EmptySD3LatentImage dimensions
        for node_id, node in wf.items():
            if node["class_type"] == "EmptySD3LatentImage":
                node["inputs"]["width"] = width
                node["inputs"]["height"] = height

        return _parameterize_workflow(
            wf, prompt, width, height, frames=0, steps=4, cfg=1.0
        )


# =============================================================================
# Imagen 4 Fast (Google API)
# =============================================================================

def generate_image_gemini(
    prompt: str,
    width: int = 480,
    height: int = 832,
    output_path: str = "/tmp/shorts/cut.png",
) -> Optional[str]:
    """Generate cut image using Google Imagen 4 Fast.

    Args:
        prompt: Image description prompt
        width: Image width (for aspect ratio calculation)
        height: Image height (for aspect ratio calculation)
        output_path: Path to save the generated image

    Returns:
        Output path if successful, None otherwise
    """
    if not GOOGLE_API_KEY:
        print("❌ GOOGLE_API_KEY 환경변수가 필요합니다 (Imagen 4 Fast)")
        return None

    aspect_ratio = "9:16" if width < height else "16:9"

    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "imagen-4.0-fast-generate-001:predict"
    )

    request_body = {
        "instances": [
            {
                "prompt": (
                    f"High-quality cinematic image: {prompt}. "
                    f"Style: photorealistic, cinematic lighting, film grain."
                ),
            }
        ],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": aspect_ratio,
            "personGeneration": "allow_adult",
        },
    }

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GOOGLE_API_KEY,
    }

    print(f"🖼️ Generating cut image with Imagen 4 Fast...")
    print(f"   Prompt: {prompt[:60]}...")
    print(f"   Aspect ratio: {aspect_ratio}")

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(request_body).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"❌ Imagen 4 Fast API Error: {e.code}")
        print(f"   Details: {error_body[:300]}")
        return None

    try:
        # Imagen 4 predict response format
        predictions = data.get("predictions", [])
        if predictions:
            image_data = predictions[0]["bytesBase64Encoded"]
        else:
            # Fallback: generatedImages format
            images = data["generatedImages"]
            image_data = images[0]["image"]["imageBytes"]
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(base64.b64decode(image_data))
        print(f"✅ Cut image saved: {output_path}")
        return output_path
    except (KeyError, IndexError) as e:
        print(f"❌ Failed to parse Imagen 4 Fast response: {e}")
        print(f"   Raw response keys: {list(data.keys())}")
        return None


# =============================================================================
# On-Demand Helpers (Phase 2 preparation)
# =============================================================================

def upload_image_to_comfyui(host: str, image_path: str) -> str:
    """Upload local image to ComfyUI instance for I2V input."""
    url = f"{host}/upload/image"
    filename = os.path.basename(image_path)

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
        return result.get("name", filename)


def submit_comfyui_workflow(host: str, workflow: dict) -> str:
    """POST /prompt — submit workflow to On-Demand ComfyUI instance."""
    url = f"{host}/prompt"
    data = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        return result["prompt_id"]


def poll_comfyui_result(host: str, prompt_id: str, max_wait: int = 600) -> Optional[dict]:
    """GET /history/{prompt_id} — poll for result."""
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
    """GET /view — download result file from On-Demand instance."""
    url = f"{host}/view?filename={filename}&type=output"
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    urllib.request.urlretrieve(url, output_path)
    return output_path


# =============================================================================
# QC / Validation
# =============================================================================

def validate_clip(clip_path: str, expected_duration: float) -> bool:
    """Validate generated video clip."""
    if not os.path.exists(clip_path):
        return False

    if os.path.getsize(clip_path) < 100 * 1024:  # 100KB minimum
        return False

    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet", "-show_entries",
                "format=duration", "-of", "csv=p=0", clip_path,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        duration = float(result.stdout.strip())
        if abs(duration - expected_duration) > 1.0:
            print(f"⚠️ Duration mismatch: {duration:.1f}s vs expected {expected_duration:.1f}s")
        return True
    except (subprocess.CalledProcessError, ValueError):
        return False


# =============================================================================
# CLI Test Entry Point
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ComfyUI Client Test")
    parser.add_argument("--test-imagen", type=str, help="Test Imagen 4 Fast image generation")
    parser.add_argument("--test-flux", type=str, help="Test FLUX.2 Klein 4B image generation")
    parser.add_argument("--output", "-o", default="/tmp/shorts/test_cut.png", help="Output path")
    args = parser.parse_args()

    if args.test_imagen:
        result = generate_image_gemini(args.test_imagen, output_path=args.output)
        if result:
            print(f"✅ Imagen 4 Fast test passed: {result}")
        else:
            print("❌ Imagen 4 Fast test failed")

    elif args.test_flux:
        client = ComfyUIClient()
        result = client.generate_image(args.test_flux, output_path=args.output)
        if result:
            print(f"✅ FLUX.2 Klein 4B test passed: {result}")
        else:
            print("❌ FLUX.2 Klein 4B test failed")

    else:
        parser.print_help()
