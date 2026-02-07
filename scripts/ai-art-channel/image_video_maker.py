#!/usr/bin/env python3
"""
이미지 → 영상 변환기 (비용 최적화)

AI 아트 이미지를 Ken Burns 효과로 Shorts 영상으로 변환합니다.
Veo 3.1 대신 FFmpeg만 사용하여 비용 $0.

Usage:
    python3 image_video_maker.py --test
    python3 image_video_maker.py --image art.jpg --output video.mp4
    python3 image_video_maker.py --images art1.jpg,art2.jpg --style slideshow
"""

import argparse
import json
import os
import random
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

# Local imports
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent / "x-to-shorts"))

from config import (
    VIDEO_FORMAT,
    KEN_BURNS_PRESETS,
    DEFAULT_HASHTAGS,
    HOOK_TEMPLATES,
    OUTPUT_DIR,
)

from text_overlay import TextOverlay, apply_text_overlays, generate_shorts_overlays


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class ImageClip:
    """단일 이미지 클립 설정"""
    image_path: str
    duration: float = 5.0
    effect: str = "zoom_in_slow"        # Ken Burns 효과
    start_time: float = 0.0             # 영상 내 시작 시간
    text_overlay: Optional[str] = None  # 오버레이 텍스트
    text_style: str = "subtitle"


@dataclass
class VideoProject:
    """영상 프로젝트 설정"""
    clips: List[ImageClip]
    output_path: str
    title: str = "AI Art Shorts"
    total_duration: float = 60.0
    background_music: Optional[str] = None
    text_overlays: List[Dict] = field(default_factory=list)
    hashtags: List[str] = field(default_factory=list)


# =============================================================================
# Ken Burns Effect Generation
# =============================================================================

def create_zoom_filter(
    scale_start: float,
    scale_end: float,
    duration: float,
    width: int = 1080,
    height: int = 1920
) -> str:
    """줌 인/아웃 필터 생성

    Ken Burns 효과의 핵심 - 시간에 따른 스케일 변화
    zoompan 필터는 'on' 변수 (현재 프레임 번호)를 사용
    """
    fps = 30
    total_frames = int(fps * duration)

    # zoompan에서 z는 'on' (프레임 번호) 기반으로 계산
    # z = scale_start + (on / total_frames) * (scale_end - scale_start)
    z_expr = f"{scale_start}+on/{total_frames}*{scale_end - scale_start}"

    # zoompan 필터 구성
    # d: 총 프레임 수
    # x, y: 중심점 (줌 시 중앙 유지)
    filter_str = (
        f"zoompan="
        f"z='{z_expr}':"
        f"d={total_frames}:"
        f"x='iw/2-(iw/zoom/2)':"
        f"y='ih/2-(ih/zoom/2)':"
        f"s={width}x{height}:"
        f"fps={fps}"
    )

    return filter_str


def create_pan_filter(
    direction: str,
    duration: float,
    width: int = 1080,
    height: int = 1920
) -> str:
    """패닝 필터 생성

    좌우/상하 이동 효과
    zoompan 필터에서 x, y는 'on' (프레임 번호) 기반
    """
    fps = 30
    total_frames = int(fps * duration)

    # 패닝은 약간의 줌 (1.2x)과 함께 위치 이동
    # x, y 계산: 이미지가 출력보다 클 때 위치 이동
    if direction == "left_to_right":
        x_expr = f"(iw-ow)/2*(1-on/{total_frames})"
        y_expr = "(ih-oh)/2"
    elif direction == "right_to_left":
        x_expr = f"(iw-ow)/2*on/{total_frames}"
        y_expr = "(ih-oh)/2"
    elif direction == "top_to_bottom":
        x_expr = "(iw-ow)/2"
        y_expr = f"(ih-oh)/2*(1-on/{total_frames})"
    elif direction == "bottom_to_top":
        x_expr = "(iw-ow)/2"
        y_expr = f"(ih-oh)/2*on/{total_frames}"
    else:
        # 기본: 왼쪽에서 오른쪽
        x_expr = f"(iw-ow)/2*(1-on/{total_frames})"
        y_expr = "(ih-oh)/2"

    filter_str = (
        f"zoompan="
        f"z=1.2:"
        f"d={total_frames}:"
        f"x='{x_expr}':"
        f"y='{y_expr}':"
        f"s={width}x{height}:"
        f"fps={fps}"
    )

    return filter_str


def get_ken_burns_filter(
    effect: str,
    duration: float,
    width: int = 1080,
    height: int = 1920
) -> str:
    """Ken Burns 효과 필터 반환"""
    preset = KEN_BURNS_PRESETS.get(effect, KEN_BURNS_PRESETS["zoom_in_slow"])

    if "scale_start" in preset:
        # 줌 효과
        return create_zoom_filter(
            preset["scale_start"],
            preset["scale_end"],
            duration,
            width,
            height
        )
    elif "x_start" in preset:
        # 패닝 효과
        return create_pan_filter(
            "left_to_right" if "left" in effect else "right_to_left",
            duration,
            width,
            height
        )
    else:
        # 기본 줌 인
        return create_zoom_filter(1.0, 1.3, duration, width, height)


# =============================================================================
# Image Processing
# =============================================================================

def prepare_image(
    image_path: str,
    output_path: str,
    target_width: int = 1080,
    target_height: int = 1920
) -> str:
    """이미지를 9:16 비율로 리사이즈/크롭

    이미지 중심을 유지하면서 세로 영상에 맞게 조정
    """
    # FFmpeg로 리사이즈 + 크롭
    cmd = [
        "ffmpeg", "-y",
        "-i", image_path,
        "-vf", (
            f"scale='if(gt(iw/ih,{target_width}/{target_height}),"
            f"-1,{target_height})':'if(gt(iw/ih,{target_width}/{target_height}),"
            f"{target_width},-1)',"
            f"crop={target_width}:{target_height},"
            f"setsar=1"
        ),
        "-q:v", "2",
        output_path
    ]

    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"❌ 이미지 처리 실패: {e.stderr.decode()[:200]}")
        return image_path


def create_clip_from_image(
    image_path: str,
    output_path: str,
    duration: float = 5.0,
    effect: str = "zoom_in_slow",
    width: int = 1080,
    height: int = 1920
) -> Optional[str]:
    """단일 이미지에서 영상 클립 생성"""

    if not os.path.exists(image_path):
        print(f"❌ 이미지 파일을 찾을 수 없습니다: {image_path}")
        return None

    print(f"   🎬 클립 생성: {os.path.basename(image_path)} ({duration}s, {effect})")

    # Ken Burns 필터 생성
    kb_filter = get_ken_burns_filter(effect, duration, width, height)

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-vf", kb_filter,
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        output_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            return output_path
        else:
            print(f"❌ FFmpeg 오류: {result.stderr[:200]}")
            return None
    except subprocess.TimeoutExpired:
        print(f"❌ 클립 생성 타임아웃")
        return None


# =============================================================================
# Video Assembly
# =============================================================================

def concatenate_clips(
    clip_paths: List[str],
    output_path: str
) -> Optional[str]:
    """여러 클립을 하나로 연결"""

    if not clip_paths:
        print("❌ 연결할 클립이 없습니다.")
        return None

    if len(clip_paths) == 1:
        # 단일 클립이면 복사
        subprocess.run(["cp", clip_paths[0], output_path], check=True)
        return output_path

    # concat demuxer용 파일 리스트 생성
    list_path = output_path + ".txt"
    with open(list_path, "w") as f:
        for clip in clip_paths:
            f.write(f"file '{clip}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_path,
        "-c", "copy",
        output_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        os.remove(list_path)  # 임시 파일 삭제
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"❌ 클립 연결 실패: {e.stderr[:200]}")
        return None


def add_audio(
    video_path: str,
    audio_path: str,
    output_path: str,
    fade_out: float = 2.0
) -> Optional[str]:
    """영상에 배경 음악 추가"""

    if not os.path.exists(audio_path):
        print(f"⚠️ 오디오 파일을 찾을 수 없습니다: {audio_path}")
        # 오디오 없이 복사
        subprocess.run(["cp", video_path, output_path], check=True)
        return output_path

    # 영상 길이 가져오기
    probe_cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True)
    duration = float(result.stdout.strip())

    # 페이드 아웃 시작점
    fade_start = duration - fade_out

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-filter_complex", (
            f"[1:a]atrim=0:{duration},"
            f"afade=t=out:st={fade_start}:d={fade_out}[aout]"
        ),
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        output_path
    ]

    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"❌ 오디오 추가 실패")
        # 오디오 없이 복사
        subprocess.run(["cp", video_path, output_path], check=True)
        return output_path


# =============================================================================
# Main Pipeline
# =============================================================================

def create_ai_art_video(
    image_paths: List[str],
    output_path: str,
    hook_text: str = "",
    hashtags: List[str] = None,
    total_duration: float = 60.0,
    effects: List[str] = None,
    audio_path: str = None
) -> Optional[str]:
    """AI 아트 이미지들로 Shorts 영상 생성

    Args:
        image_paths: 이미지 파일 경로 목록
        output_path: 출력 영상 경로
        hook_text: 훅 텍스트 (첫 3초)
        hashtags: 해시태그 목록
        total_duration: 총 영상 길이
        effects: Ken Burns 효과 목록 (이미지 수와 동일)
        audio_path: 배경 음악 경로 (선택)

    Returns:
        생성된 영상 경로 또는 None
    """
    if not image_paths:
        print("❌ 이미지가 없습니다.")
        return None

    if hashtags is None:
        hashtags = DEFAULT_HASHTAGS

    print("=" * 60)
    print("🎨 AI Art Video Maker")
    print("=" * 60)

    # 출력 디렉토리 생성
    output_dir = os.path.dirname(output_path) or OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)
    temp_dir = os.path.join(output_dir, "temp")
    os.makedirs(temp_dir, exist_ok=True)

    # 이미지당 지속 시간 계산
    num_images = len(image_paths)
    duration_per_image = total_duration / num_images

    # 효과 목록 (지정 안되면 랜덤)
    if effects is None:
        effect_options = list(KEN_BURNS_PRESETS.keys())
        effects = [random.choice(effect_options) for _ in image_paths]

    print(f"\n[1/4] 🖼️  이미지 처리 중... ({num_images}개)")

    # 각 이미지에서 클립 생성
    clip_paths = []
    for i, img_path in enumerate(image_paths):
        effect = effects[i] if i < len(effects) else "zoom_in_slow"
        clip_path = os.path.join(temp_dir, f"clip_{i:02d}.mp4")

        result = create_clip_from_image(
            img_path,
            clip_path,
            duration=duration_per_image,
            effect=effect
        )

        if result:
            clip_paths.append(result)

    if not clip_paths:
        print("❌ 생성된 클립이 없습니다.")
        return None

    print(f"\n[2/4] 🔗 클립 연결 중...")
    raw_video_path = os.path.join(temp_dir, "raw_video.mp4")
    concat_result = concatenate_clips(clip_paths, raw_video_path)

    if not concat_result:
        return None

    # 텍스트 오버레이 적용
    print(f"\n[3/4] 🔤 텍스트 오버레이 적용 중...")

    overlays = generate_shorts_overlays(
        hook_text=hook_text,
        hashtags=hashtags,
        duration=total_duration
    )

    text_video_path = os.path.join(temp_dir, "with_text.mp4")
    text_result = apply_text_overlays(
        video_path=raw_video_path,
        overlays=overlays,
        output_path=text_video_path
    )

    if not text_result:
        text_result = raw_video_path

    # 오디오 추가 (선택)
    if audio_path:
        print(f"\n[4/4] 🎵 오디오 추가 중...")
        final_result = add_audio(text_result, audio_path, output_path)
    else:
        print(f"\n[4/4] 📦 최종 영상 생성 중...")
        subprocess.run(["cp", text_result, output_path], check=True)
        final_result = output_path

    # 임시 파일 정리
    for clip in clip_paths:
        try:
            os.remove(clip)
        except:
            pass

    print()
    print("=" * 60)
    print(f"✅ 영상 생성 완료: {final_result}")
    print(f"   이미지: {num_images}개")
    print(f"   길이: {total_duration}초")
    print(f"   비용: $0.00 (FFmpeg only)")
    print("=" * 60)

    return final_result


def create_single_image_video(
    image_path: str,
    output_path: str,
    hook_text: str = "",
    hashtags: List[str] = None,
    duration: float = 60.0
) -> Optional[str]:
    """단일 이미지로 Shorts 영상 생성 (다양한 효과 조합)"""

    if not os.path.exists(image_path):
        print(f"❌ 이미지를 찾을 수 없습니다: {image_path}")
        return None

    # 단일 이미지를 여러 효과로 분할
    # 60초를 4-5개 구간으로 나눔
    effects_sequence = [
        "zoom_in_slow",
        "pan_left_to_right",
        "zoom_out_slow",
        "diagonal_zoom",
    ]

    # 같은 이미지를 여러 번 사용
    image_paths = [image_path] * len(effects_sequence)

    return create_ai_art_video(
        image_paths=image_paths,
        output_path=output_path,
        hook_text=hook_text,
        hashtags=hashtags,
        total_duration=duration,
        effects=effects_sequence
    )


# =============================================================================
# CLI Interface
# =============================================================================

def run_test():
    """테스트 실행"""
    print("=" * 60)
    print("🧪 IMAGE VIDEO MAKER TEST")
    print("=" * 60)

    # 테스트 이미지 생성 (FFmpeg로 간단한 색상 이미지)
    test_dir = "/tmp/ai-art-test"
    os.makedirs(test_dir, exist_ok=True)

    # 테스트용 더미 이미지 생성
    test_images = []
    colors = ["red", "blue", "green", "orange"]

    print("\n[1/3] 🎨 테스트 이미지 생성 중...")
    for i, color in enumerate(colors):
        img_path = os.path.join(test_dir, f"test_{color}.png")

        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c={color}:s=1080x1920:d=1",
            "-vf", f"drawtext=text='AI Art {i+1}':fontsize=72:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
            "-frames:v", "1",
            img_path
        ]

        try:
            subprocess.run(cmd, capture_output=True, check=True)
            test_images.append(img_path)
            print(f"   ✅ {color}.png")
        except:
            print(f"   ⚠️ {color}.png 생성 실패 (폰트 없을 수 있음)")
            # 폰트 없이 재시도
            cmd_no_text = [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", f"color=c={color}:s=1080x1920:d=1",
                "-frames:v", "1",
                img_path
            ]
            subprocess.run(cmd_no_text, capture_output=True)
            test_images.append(img_path)
            print(f"   ✅ {color}.png (텍스트 없음)")

    if not test_images:
        print("❌ 테스트 이미지 생성 실패")
        return

    print(f"\n[2/3] 🎬 테스트 영상 생성 중...")
    output_path = os.path.join(test_dir, "test_output.mp4")

    result = create_ai_art_video(
        image_paths=test_images[:2],  # 테스트용 2개만
        output_path=output_path,
        hook_text="AI 아트 테스트 영상",
        hashtags=["#테스트", "#AI아트"],
        total_duration=10.0  # 짧은 테스트
    )

    print(f"\n[3/3] 📊 결과 확인")
    if result and os.path.exists(result):
        size_mb = os.path.getsize(result) / (1024 * 1024)
        print(f"   ✅ 영상 생성 성공")
        print(f"   파일: {result}")
        print(f"   크기: {size_mb:.2f} MB")
    else:
        print(f"   ❌ 영상 생성 실패")

    print("\n" + "=" * 60)
    print("✅ Test complete")
    print(f"\n   결과 확인: open {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="이미지 → 영상 변환기 (Ken Burns 효과)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 테스트 실행
  python3 image_video_maker.py --test

  # 단일 이미지로 60초 영상
  python3 image_video_maker.py --image art.jpg --output video.mp4

  # 여러 이미지로 슬라이드쇼
  python3 image_video_maker.py --images "a.jpg,b.jpg,c.jpg" --duration 60

  # 훅 텍스트 추가
  python3 image_video_maker.py --image art.jpg --hook "AI가 그린 고양이 실화냐?"

Ken Burns 효과:
  zoom_in_slow      - 천천히 줌인 (드라마틱)
  zoom_out_slow     - 천천히 줌아웃 (전체 공개)
  pan_left_to_right - 왼쪽→오른쪽 패닝
  pan_right_to_left - 오른쪽→왼쪽 패닝
  diagonal_zoom     - 대각선 줌 (역동적)
"""
    )

    parser.add_argument("--test", "-t", action="store_true", help="테스트 실행")
    parser.add_argument("--image", "-i", help="단일 이미지 경로")
    parser.add_argument("--images", help="여러 이미지 (쉼표 구분)")
    parser.add_argument("--output", "-o", default="/tmp/ai-art-video.mp4", help="출력 경로")
    parser.add_argument("--duration", "-d", type=float, default=60.0, help="총 영상 길이 (초)")
    parser.add_argument("--hook", help="훅 텍스트 (첫 3초)")
    parser.add_argument("--effect", "-e", choices=list(KEN_BURNS_PRESETS.keys()),
                        help="Ken Burns 효과")
    parser.add_argument("--audio", "-a", help="배경 음악 경로")
    parser.add_argument("--hashtags", help="해시태그 (쉼표 구분)")

    args = parser.parse_args()

    if args.test:
        run_test()
        return

    # 이미지 목록 구성
    image_paths = []
    if args.image:
        image_paths = [args.image]
    elif args.images:
        image_paths = [p.strip() for p in args.images.split(",")]

    if not image_paths:
        parser.print_help()
        return

    # 해시태그 파싱
    hashtags = None
    if args.hashtags:
        hashtags = [h.strip() for h in args.hashtags.split(",")]

    # 효과 목록
    effects = None
    if args.effect:
        effects = [args.effect] * len(image_paths)

    # 영상 생성
    if len(image_paths) == 1:
        result = create_single_image_video(
            image_path=image_paths[0],
            output_path=args.output,
            hook_text=args.hook or "",
            hashtags=hashtags,
            duration=args.duration
        )
    else:
        result = create_ai_art_video(
            image_paths=image_paths,
            output_path=args.output,
            hook_text=args.hook or "",
            hashtags=hashtags,
            total_duration=args.duration,
            effects=effects,
            audio_path=args.audio
        )

    if result:
        print(f"\n🎬 결과: {result}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
