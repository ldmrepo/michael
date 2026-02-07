#!/usr/bin/env python3
"""
Agentic Video Generation Pipeline for YouTube Shorts (2026)

Workflow:
1. Creative Brief → Beat Sheet (구조 생성)
2. Beat Sheet → Shot List (씬별 상세)
3. Shot List → Continuity Table (일관성 관리)
4. Prompt Chain → Video Generation (Veo 3.1)
5. Clips → Final Video (FFmpeg)

Usage:
    python3 agentic_video.py --brief "60초 커피 모닝 루틴 쇼츠"
    python3 agentic_video.py --brief "우주 여행 영상" --style cinematic
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from pathlib import Path

# Import local video generator
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class Shot:
    """8-Point Shot Grammar"""
    id: int
    subject: str          # 피사체
    emotion: str          # 감정/분위기
    optics: str           # 렌즈/샷 타입
    motion: str           # 카메라 움직임
    lighting: str         # 조명
    style: str            # 시각 스타일
    audio: str            # 사운드
    continuity: str       # 연속성 지시
    duration: int = 8     # 초 (Veo 3.1: 4, 6, 8만 지원)
    rendering_hint: str = "i2v"       # i2v, t2v, flf2v (Phase 2)
    reference_image: str = ""          # I2V 레퍼런스 이미지 경로

    def __post_init__(self):
        """Normalize duration to valid values per provider"""
        VALID_DURATIONS = [4, 6, 8]
        self.duration = min(VALID_DURATIONS, key=lambda x: abs(x - self.duration))

    def to_prompt(self) -> str:
        """Convert to Veo 3.1 prompt"""
        return f"""{self.subject}, {self.emotion} mood.
{self.optics}, {self.motion}.
{self.lighting}, {self.style}.
Audio: {self.audio}.
{self.continuity}"""


@dataclass
class BeatSheet:
    """Story structure for video"""
    hook: str              # 0-3초: 시선 끌기
    setup: str             # 3-15초: 상황 설정
    development: str       # 15-40초: 전개
    climax: str            # 40-50초: 클라이맥스
    resolution: str        # 50-60초: 마무리/CTA
    total_duration: int = 60


@dataclass
class ContinuityTable:
    """Maintains consistency across shots"""
    character: str = ""
    wardrobe: str = ""
    props: List[str] = field(default_factory=list)
    color_palette: str = ""
    lighting_setup: str = ""
    time_of_day: str = ""
    weather: str = ""
    camera_style: str = ""
    audio_theme: str = ""


@dataclass
class VideoProject:
    """Complete video project"""
    brief: str
    beat_sheet: Optional[BeatSheet] = None
    shots: List[Shot] = field(default_factory=list)
    continuity: Optional[ContinuityTable] = None
    clips: List[str] = field(default_factory=list)
    output_path: str = ""


# =============================================================================
# AI Agents (Claude-powered)
# =============================================================================

def call_claude(prompt: str, system: str = "") -> str:
    """Call Claude CLI for AI generation"""
    full_prompt = prompt
    if system:
        full_prompt = f"[System: {system}]\n\n{prompt}"

    try:
        result = subprocess.run(
            ["claude", "-p", "--output-format", "text"],
            input=full_prompt,
            capture_output=True,
            text=True,
            timeout=120
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        print("⚠️ Claude timeout, using fallback")
        return ""
    except FileNotFoundError:
        print("⚠️ Claude CLI not found, using fallback")
        return ""


def generate_beat_sheet(brief: str) -> BeatSheet:
    """Agent 1: Generate story beat sheet from brief"""
    print("📝 Generating Beat Sheet...")

    prompt = f"""Create a beat sheet for a 60-second YouTube Short video.

Brief: {brief}

Output ONLY valid JSON in this exact format:
{{
    "hook": "0-3초 훅 설명 (시선 끌기, 충격적/호기심)",
    "setup": "3-15초 상황 설정",
    "development": "15-40초 전개 (핵심 내용)",
    "climax": "40-50초 클라이맥스 (가장 인상적 장면)",
    "resolution": "50-60초 마무리/CTA"
}}

JSON only, no explanation:"""

    response = call_claude(prompt, "You are a professional video director. Output only valid JSON.")

    try:
        # Extract JSON from response
        json_str = response
        if "```" in response:
            json_str = response.split("```")[1]
            if json_str.startswith("json"):
                json_str = json_str[4:]

        data = json.loads(json_str.strip())
        return BeatSheet(**data)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"⚠️ Parse error, using default beat sheet: {e}")
        return BeatSheet(
            hook=f"Dramatic opening of {brief}",
            setup=f"Establishing the scene for {brief}",
            development=f"Main content showing {brief}",
            climax=f"Peak moment of {brief}",
            resolution=f"Satisfying conclusion of {brief}"
        )


def generate_shot_list(beat_sheet: BeatSheet, continuity: ContinuityTable, style: str = "cinematic") -> List[Shot]:
    """Agent 2: Generate detailed shot list from beat sheet"""
    print("🎬 Generating Shot List...")

    prompt = f"""Create a shot list for a 60-second YouTube Short.

Beat Sheet:
- Hook (0-3s): {beat_sheet.hook}
- Setup (3-15s): {beat_sheet.setup}
- Development (15-40s): {beat_sheet.development}
- Climax (40-50s): {beat_sheet.climax}
- Resolution (50-60s): {beat_sheet.resolution}

Continuity Requirements:
- Color Palette: {continuity.color_palette}
- Lighting: {continuity.lighting_setup}
- Time of Day: {continuity.time_of_day}
- Style: {style}

Generate 7-8 shots. Output ONLY valid JSON array:
[
    {{
        "id": 1,
        "subject": "main subject description",
        "emotion": "mood/feeling",
        "optics": "shot type and lens",
        "motion": "camera movement",
        "lighting": "lighting description",
        "style": "visual style",
        "audio": "sound description",
        "continuity": "how it connects to next shot",
        "duration": 8
    }}
]

JSON array only:"""

    response = call_claude(prompt, "You are a cinematographer. Output only valid JSON array.")

    try:
        json_str = response
        if "```" in response:
            json_str = response.split("```")[1]
            if json_str.startswith("json"):
                json_str = json_str[4:]

        data = json.loads(json_str.strip())
        return [Shot(**shot) for shot in data]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"⚠️ Parse error, generating default shots: {e}")
        return generate_default_shots(beat_sheet, style)


def generate_default_shots(beat_sheet: BeatSheet, style: str) -> List[Shot]:
    """Fallback shot generation - uses only valid Veo 3.1 durations (4, 6, 8 seconds)"""
    base_style = "cinematic, film grain, shallow depth of field" if style == "cinematic" else "vibrant, high contrast"

    return [
        Shot(1, beat_sheet.hook, "intriguing", "extreme close-up, macro", "slow push in",
             "dramatic rim lighting", base_style, "tension building sound", "hook to grab attention", 4),  # 4s hook
        Shot(2, beat_sheet.setup, "establishing", "wide shot", "slow pan right",
             "natural ambient light", base_style, "ambient atmosphere", "establishes context", 8),
        Shot(3, beat_sheet.development, "engaging", "medium shot", "tracking shot",
             "soft diffused light", base_style, "gentle background music", "develops the story", 8),
        Shot(4, beat_sheet.development, "focused", "close-up", "dolly in",
             "warm side lighting", base_style, "music builds", "highlights detail", 8),
        Shot(5, beat_sheet.development, "dynamic", "medium wide", "crane up",
             "golden hour glow", base_style, "music continues", "adds variety", 8),
        Shot(6, beat_sheet.climax, "intense", "dramatic angle", "slow motion",
             "dramatic contrast", base_style, "music peaks", "climactic moment", 8),
        Shot(7, beat_sheet.resolution, "satisfying", "wide establishing", "gentle pull back",
             "warm inviting light", base_style, "music resolves", "conclusion", 6),  # 6s transition
        Shot(8, beat_sheet.resolution, "memorable", "beauty shot", "static or slow drift",
             "perfect lighting", base_style, "fade out", "loop-friendly ending", 8),
    ]


def generate_continuity_table(brief: str, style: str) -> ContinuityTable:
    """Agent 3: Generate continuity table for consistency"""
    print("📋 Generating Continuity Table...")

    prompt = f"""Create a continuity table for visual consistency in a video.

Brief: {brief}
Style: {style}

Output ONLY valid JSON:
{{
    "character": "main subject description",
    "wardrobe": "clothing/appearance if applicable",
    "props": ["prop1", "prop2"],
    "color_palette": "main colors",
    "lighting_setup": "consistent lighting approach",
    "time_of_day": "time setting",
    "weather": "weather/atmosphere",
    "camera_style": "overall camera approach",
    "audio_theme": "audio/music theme"
}}

JSON only:"""

    response = call_claude(prompt, "You are a continuity supervisor. Output only valid JSON.")

    try:
        json_str = response
        if "```" in response:
            json_str = response.split("```")[1]
            if json_str.startswith("json"):
                json_str = json_str[4:]

        data = json.loads(json_str.strip())
        return ContinuityTable(**data)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"⚠️ Parse error, using default continuity: {e}")
        return ContinuityTable(
            color_palette="warm tones" if "coffee" in brief.lower() or "morning" in brief.lower() else "cinematic colors",
            lighting_setup="natural soft lighting",
            time_of_day="golden hour",
            camera_style=style,
            audio_theme="ambient atmospheric"
        )


# =============================================================================
# Video Generation (Veo 3.1)
# =============================================================================

def generate_clip(shot: Shot, output_path: str, reference_frame: Optional[str] = None, provider: Optional[str] = None) -> Optional[str]:
    """Generate a single video clip using Veo or Sora"""
    # Import from same directory
    import importlib.util
    spec = importlib.util.spec_from_file_location("generate_video", SCRIPT_DIR / "generate-video.py")
    if spec is None or spec.loader is None:
        print("❌ Could not load generate-video.py")
        return None
    gen_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen_module)
    generate_video = gen_module.generate_video

    prompt = shot.to_prompt()
    provider_name = (provider or "veo").upper()
    print(f"\n🎥 Generating Shot {shot.id}: {shot.subject[:50]}...")
    print(f"   Provider: {provider_name}")
    print(f"   Duration: {shot.duration}s")

    result = generate_video(
        prompt=prompt,
        duration=shot.duration,
        output_path=output_path,
        aspect_ratio="9:16",
        provider=provider
    )

    return result


def extract_last_frame(video_path: str, output_path: str) -> bool:
    """Extract the last frame from a video for continuity reference"""
    try:
        subprocess.run([
            "ffmpeg", "-y", "-sseof", "-1", "-i", video_path,
            "-vframes", "1", "-q:v", "2", output_path
        ], capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


# =============================================================================
# Video Concatenation (FFmpeg)
# =============================================================================

def concat_clips(clips: List[str], output_path: str, transition: str = "fade",
                 transition_duration: float = 0.3) -> Optional[str]:
    """Concatenate video clips with transitions"""
    print(f"\n🔗 Concatenating {len(clips)} clips...")

    if not clips:
        print("❌ No clips to concatenate")
        return None

    if len(clips) == 1:
        # Single clip, just copy
        subprocess.run(["cp", clips[0], output_path], check=True)
        return output_path

    # Create file list for concat
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        for clip in clips:
            f.write(f"file '{clip}'\n")
        filelist = f.name

    try:
        if transition == "none":
            # Simple concatenation
            subprocess.run([
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", filelist, "-c", "copy", output_path
            ], capture_output=True, check=True)
        else:
            # With crossfade transitions
            # Build complex filter for xfade
            inputs = []
            filter_parts = []

            for i, clip in enumerate(clips):
                inputs.extend(["-i", clip])

            # Calculate offsets and build xfade chain
            current_output = "[0:v]"
            offset = 0

            for i in range(1, len(clips)):
                # Get duration of previous clip
                duration_cmd = subprocess.run([
                    "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1", clips[i-1]
                ], capture_output=True, text=True)
                clip_duration = float(duration_cmd.stdout.strip())

                offset += clip_duration - transition_duration
                next_output = f"[v{i}]" if i < len(clips) - 1 else "[outv]"

                filter_parts.append(
                    f"{current_output}[{i}:v]xfade=transition={transition}:"
                    f"duration={transition_duration}:offset={offset}{next_output}"
                )
                current_output = next_output

            filter_complex = ";".join(filter_parts)

            # Handle audio concatenation
            audio_inputs = "".join([f"[{i}:a]" for i in range(len(clips))])
            filter_complex += f";{audio_inputs}concat=n={len(clips)}:v=0:a=1[outa]"

            cmd = [
                "ffmpeg", "-y",
                *inputs,
                "-filter_complex", filter_complex,
                "-map", "[outv]", "-map", "[outa]",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",  # 호환성을 위해 yuv420p 강제
                "-preset", "fast", "-crf", "18",
                "-c:a", "aac", "-b:a", "128k",
                output_path
            ]

            subprocess.run(cmd, capture_output=True, check=True)

        print(f"✅ Concatenation complete: {output_path}")
        return output_path

    except subprocess.CalledProcessError as e:
        print(f"❌ Concatenation failed: {e}")
        # Fallback to simple concat
        try:
            subprocess.run([
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", filelist, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", output_path
            ], capture_output=True, check=True)
            return output_path
        except:
            return None
    finally:
        os.unlink(filelist)


# =============================================================================
# Main Pipeline
# =============================================================================

def run_pipeline(
    brief: str,
    output_dir: str = "/tmp/shorts",
    style: str = "cinematic",
    transition: str = "fade",
    max_clips: int = 8,
    dry_run: bool = False,
    provider: Optional[str] = None
) -> Optional[str]:
    """
    Run the complete agentic video generation pipeline.

    Args:
        brief: Creative brief describing the video
        output_dir: Directory for output files
        style: Visual style (cinematic, vibrant, minimal, etc.)
        transition: Transition type (fade, dissolve, wipeleft, none)
        max_clips: Maximum number of clips to generate
        dry_run: If True, only generate plans without video
        provider: Video provider ('veo' or 'sora')

    Returns:
        Path to final video or None if failed
    """
    provider_name = (provider or "veo").upper()
    print("=" * 60)
    print("🎬 AGENTIC VIDEO GENERATION PIPELINE")
    print("=" * 60)
    print(f"Brief: {brief}")
    print(f"Style: {style}")
    print(f"Provider: {provider_name}")
    print(f"Output: {output_dir}")
    print("=" * 60)

    # Create project
    project = VideoProject(brief=brief)
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: Generate Continuity Table
    print("\n[1/5] 📋 Continuity Table")
    project.continuity = generate_continuity_table(brief, style)
    print(f"   Color: {project.continuity.color_palette}")
    print(f"   Lighting: {project.continuity.lighting_setup}")
    print(f"   Time: {project.continuity.time_of_day}")

    # Step 2: Generate Beat Sheet
    print("\n[2/5] 📝 Beat Sheet")
    project.beat_sheet = generate_beat_sheet(brief)
    print(f"   Hook: {project.beat_sheet.hook[:50]}...")
    print(f"   Climax: {project.beat_sheet.climax[:50]}...")

    # Step 3: Generate Shot List
    print("\n[3/5] 🎬 Shot List")
    project.shots = generate_shot_list(project.beat_sheet, project.continuity, style)
    project.shots = project.shots[:max_clips]  # Limit clips
    print(f"   Generated {len(project.shots)} shots")

    for shot in project.shots:
        print(f"   Shot {shot.id}: {shot.optics} - {shot.subject[:30]}...")

    # Save project plan
    plan_path = os.path.join(output_dir, "project_plan.json")
    with open(plan_path, "w") as f:
        json.dump({
            "brief": project.brief,
            "continuity": asdict(project.continuity),
            "beat_sheet": asdict(project.beat_sheet),
            "shots": [asdict(s) for s in project.shots]
        }, f, ensure_ascii=False, indent=2)
    print(f"\n📄 Plan saved: {plan_path}")

    if dry_run:
        print("\n🏁 Dry run complete. No videos generated.")
        return plan_path

    # Step 4: Generate Video Clips
    print("\n[4/5] 🎥 Generating Clips")
    reference_frame = None

    for i, shot in enumerate(project.shots):
        clip_path = os.path.join(output_dir, f"clip_{shot.id:02d}.mp4")

        result = generate_clip(shot, clip_path, reference_frame, provider)

        if result:
            project.clips.append(result)
            # Extract last frame for continuity (optional)
            frame_path = os.path.join(output_dir, f"frame_{shot.id:02d}.jpg")
            if extract_last_frame(result, frame_path):
                reference_frame = frame_path
            print(f"   ✅ Shot {shot.id} complete")
        else:
            print(f"   ❌ Shot {shot.id} failed")

    if not project.clips:
        print("\n❌ No clips generated")
        return None

    # Step 5: Concatenate
    print("\n[5/5] 🔗 Final Assembly")
    timestamp = int(time.time())
    final_path = os.path.join(output_dir, f"final_{timestamp}.mp4")

    result = concat_clips(project.clips, final_path, transition)

    if result:
        project.output_path = result

        # Get final video info
        duration_cmd = subprocess.run([
            "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", result
        ], capture_output=True, text=True)

        try:
            duration = float(duration_cmd.stdout.strip())
        except:
            duration = 0

        size_mb = os.path.getsize(result) / (1024 * 1024)

        print("\n" + "=" * 60)
        print("🎉 PIPELINE COMPLETE!")
        print("=" * 60)
        print(f"📁 Output: {result}")
        print(f"⏱️  Duration: {duration:.1f}s")
        print(f"📊 Size: {size_mb:.2f} MB")
        print(f"🎬 Clips: {len(project.clips)}")
        print("=" * 60)

        return result

    return None


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Agentic Video Generation Pipeline for YouTube Shorts"
    )
    parser.add_argument(
        "--brief", "-b", required=True,
        help="Creative brief describing the video"
    )
    parser.add_argument(
        "--output", "-o", default="/tmp/shorts",
        help="Output directory (default: /tmp/shorts)"
    )
    parser.add_argument(
        "--style", "-s", default="cinematic",
        choices=["cinematic", "vibrant", "minimal", "retro", "dark"],
        help="Visual style (default: cinematic)"
    )
    parser.add_argument(
        "--transition", "-t", default="fade",
        choices=["fade", "dissolve", "wipeleft", "wiperight", "none"],
        help="Transition type (default: fade)"
    )
    parser.add_argument(
        "--max-clips", "-m", type=int, default=8,
        help="Maximum clips to generate (default: 8)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Only generate plan, don't create videos"
    )
    parser.add_argument(
        "--provider", "-p",
        choices=["veo", "sora", "comfyui"],
        default=None,
        help="Video provider: veo (default), sora, or comfyui"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output result as JSON"
    )

    args = parser.parse_args()

    result = run_pipeline(
        brief=args.brief,
        output_dir=args.output,
        style=args.style,
        transition=args.transition,
        max_clips=args.max_clips,
        dry_run=args.dry_run,
        provider=args.provider
    )

    if args.json:
        output = {
            "success": result is not None,
            "output_path": result,
            "brief": args.brief,
            "style": args.style
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))

    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
