#!/usr/bin/env python3
"""Add TTS narration and/or background music to video."""

import argparse
import json
import os
import subprocess
import sys
import urllib.request


def generate_tts(text: str, output_path: str, voice: str = "nova", speed: float = 0.9):
    """Generate TTS audio using OpenAI API.

    Args:
        text: Text to convert to speech
        output_path: Path to save the audio file
        voice: OpenAI TTS voice (alloy, echo, fable, onyx, nova, shimmer)
        speed: Speech speed (0.25 to 4.0)

    Returns:
        True if successful, False otherwise
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not set")
        return False

    print(f"🎙️ Generating TTS audio...")
    print(f"   Voice: {voice}")
    print(f"   Speed: {speed}")
    print(f"   Text length: {len(text)} chars")

    request_body = {
        "model": "tts-1",
        "input": text,
        "voice": voice,
        "speed": speed,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/audio/speech",
        data=json.dumps(request_body).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as response:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(response.read())

        size_kb = os.path.getsize(output_path) / 1024
        print(f"✅ TTS audio saved: {output_path} ({size_kb:.1f} KB)")
        return True
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"❌ TTS API error: {e.code}")
        print(f"   Details: {error_body[:200]}")
        return False


def get_duration(file_path: str) -> float:
    """Get duration of audio/video file in seconds."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", file_path],
        capture_output=True,
        text=True
    )
    return float(result.stdout.strip())


def merge_audio_video(
    video_path: str,
    audio_path: str,
    output_path: str,
    bgm_path: str = None,
    bgm_volume: float = 0.3,
):
    """Merge audio with video using ffmpeg.

    Args:
        video_path: Path to input video
        audio_path: Path to TTS audio (optional, can be None)
        output_path: Path to output video
        bgm_path: Path to background music (optional)
        bgm_volume: Background music volume (0.0 to 1.0)

    Returns:
        True if successful, False otherwise
    """
    print(f"🎬 Merging audio with video...")

    # Get video duration
    video_duration = get_duration(video_path)
    print(f"   Video duration: {video_duration:.1f}s")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Build ffmpeg command
    inputs = ["-i", video_path]
    filter_parts = []

    if audio_path and os.path.exists(audio_path):
        inputs.extend(["-i", audio_path])
        audio_duration = get_duration(audio_path)
        print(f"   Audio duration: {audio_duration:.1f}s")

        # If audio is longer than video, we need to extend video or trim audio
        if audio_duration > video_duration:
            print(f"   ⚠️ Audio longer than video, trimming audio")
            filter_parts.append(f"[1:a]atrim=0:{video_duration}[narration]")
        else:
            filter_parts.append("[1:a]acopy[narration]")

    if bgm_path and os.path.exists(bgm_path):
        inputs.extend(["-i", bgm_path])
        bgm_index = 2 if audio_path else 1
        # Loop BGM to match video duration and adjust volume
        filter_parts.append(
            f"[{bgm_index}:a]aloop=loop=-1:size=2e+09,atrim=0:{video_duration},"
            f"volume={bgm_volume}[bgm]"
        )

    # Build final audio mix
    if audio_path and bgm_path:
        filter_parts.append("[narration][bgm]amix=inputs=2:duration=first[aout]")
        audio_map = "[aout]"
    elif audio_path:
        audio_map = "[narration]"
    elif bgm_path:
        audio_map = "[bgm]"
    else:
        # No audio to add
        print("❌ No audio sources provided")
        return False

    filter_complex = ";".join(filter_parts)

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", audio_map,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        output_path
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"✅ Video with audio saved: {output_path} ({size_mb:.2f} MB)")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg error: {e.stderr.decode()[:500]}")
        return False


def add_audio_to_video(
    video_path: str,
    output_path: str,
    script: str = None,
    voice: str = "nova",
    speed: float = 0.9,
    bgm_path: str = None,
    bgm_volume: float = 0.3,
):
    """Add TTS narration and/or background music to video.

    Args:
        video_path: Path to input video
        output_path: Path to output video
        script: Text for TTS narration (optional)
        voice: TTS voice
        speed: TTS speed
        bgm_path: Path to background music (optional)
        bgm_volume: Background music volume

    Returns:
        Output path if successful, None otherwise
    """
    if not os.path.exists(video_path):
        print(f"❌ Video not found: {video_path}")
        return None

    audio_path = None

    # Generate TTS if script provided
    if script:
        audio_path = output_path.replace(".mp4", "_tts.mp3")
        if not generate_tts(script, audio_path, voice, speed):
            return None

    # Merge audio with video
    if not merge_audio_video(video_path, audio_path, output_path, bgm_path, bgm_volume):
        return None

    # Cleanup temp TTS file
    if audio_path and os.path.exists(audio_path):
        os.remove(audio_path)

    return output_path


def main():
    parser = argparse.ArgumentParser(description="Add audio to video")
    parser.add_argument("--video", "-v", required=True, help="Input video path")
    parser.add_argument("--output", "-o", required=True, help="Output video path")
    parser.add_argument("--script", "-s", help="Text for TTS narration")
    parser.add_argument("--script-file", help="File containing TTS script")
    parser.add_argument("--voice", default="nova",
                       choices=["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
                       help="TTS voice (default: nova)")
    parser.add_argument("--speed", type=float, default=0.9, help="TTS speed (default: 0.9)")
    parser.add_argument("--bgm", help="Background music file path")
    parser.add_argument("--bgm-volume", type=float, default=0.3, help="BGM volume (default: 0.3)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    # Get script from file if specified
    script = args.script
    if args.script_file and os.path.exists(args.script_file):
        with open(args.script_file, "r") as f:
            script = f.read()

    result = add_audio_to_video(
        video_path=args.video,
        output_path=args.output,
        script=script,
        voice=args.voice,
        speed=args.speed,
        bgm_path=args.bgm,
        bgm_volume=args.bgm_volume,
    )

    if args.json:
        output = {
            "success": result is not None,
            "output_path": result,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    elif result:
        print(f"\n🎉 Audio added successfully!")
        print(f"   Path: {result}")


if __name__ == "__main__":
    main()
