#!/usr/bin/env python3
"""
영상 텍스트 오버레이 도구

Veo 3.1로 생성된 텍스트 없는 영상에 정확한 한글 텍스트를 오버레이합니다.

Usage:
    # 단일 텍스트 추가
    python3 text_overlay.py --video input.mp4 --text "헐, 실화냐?" --style hook

    # JSON 설정 파일 사용
    python3 text_overlay.py --video input.mp4 --config overlays.json

    # 테스트
    python3 text_overlay.py --test
"""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional


# =============================================================================
# Constants
# =============================================================================

# 한글 폰트 경로 (macOS 기준)
FONT_PATHS = {
    "macos": {
        "default": "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "bold": "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
        "noto": "/Library/Fonts/NotoSansKR-Regular.otf",
        "noto_bold": "/Library/Fonts/NotoSansKR-Bold.otf",
    },
    "linux": {
        "default": "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "bold": "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    }
}

# 스타일 프리셋
STYLE_PRESETS = {
    "hook": {
        "description": "첫 3초 훅 텍스트 (크고 강렬)",
        "fontsize": 72,
        "fontcolor": "yellow",
        "borderw": 4,
        "bordercolor": "black",
        "shadowx": 3,
        "shadowy": 3,
        "shadowcolor": "black@0.5",
        "position": "center",
        "animation": "pop",
    },
    "subtitle": {
        "description": "자막 스타일 (하단, 가독성 중심)",
        "fontsize": 42,
        "fontcolor": "white",
        "borderw": 3,
        "bordercolor": "black",
        "shadowx": 2,
        "shadowy": 2,
        "shadowcolor": "black@0.7",
        "position": "bottom",
        "animation": "fade",
    },
    "caption": {
        "description": "캡션 스타일 (상단, 정보 표시)",
        "fontsize": 36,
        "fontcolor": "white",
        "borderw": 2,
        "bordercolor": "black",
        "shadowx": 1,
        "shadowy": 1,
        "shadowcolor": "black@0.5",
        "position": "top",
        "animation": "fade",
    },
    "hashtag": {
        "description": "해시태그 스타일 (하단, 작은 크기)",
        "fontsize": 28,
        "fontcolor": "cyan",
        "borderw": 2,
        "bordercolor": "black",
        "shadowx": 1,
        "shadowy": 1,
        "shadowcolor": "black@0.5",
        "position": "bottom_left",
        "animation": "slide",
    },
    "emphasis": {
        "description": "강조 텍스트 (빨간색, 중앙)",
        "fontsize": 56,
        "fontcolor": "red",
        "borderw": 3,
        "bordercolor": "white",
        "shadowx": 2,
        "shadowy": 2,
        "shadowcolor": "black@0.7",
        "position": "center",
        "animation": "pop",
    },
    "minimal": {
        "description": "미니멀 스타일 (감성형 영상용)",
        "fontsize": 32,
        "fontcolor": "white@0.9",
        "borderw": 0,
        "bordercolor": "transparent",
        "shadowx": 2,
        "shadowy": 2,
        "shadowcolor": "black@0.3",
        "position": "center",
        "animation": "fade",
    },
}

# 위치 프리셋 (9:16 세로 영상 기준)
POSITION_PRESETS = {
    "top": "x=(w-text_w)/2:y=h*0.08",
    "top_left": "x=w*0.05:y=h*0.08",
    "top_right": "x=w*0.95-text_w:y=h*0.08",
    "center": "x=(w-text_w)/2:y=(h-text_h)/2",
    "center_left": "x=w*0.05:y=(h-text_h)/2",
    "center_right": "x=w*0.95-text_w:y=(h-text_h)/2",
    "bottom": "x=(w-text_w)/2:y=h*0.88",
    "bottom_left": "x=w*0.05:y=h*0.88",
    "bottom_right": "x=w*0.95-text_w:y=h*0.88",
}


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class TextOverlay:
    """텍스트 오버레이 설정"""
    text: str
    start_time: float           # 시작 시간 (초)
    end_time: float             # 종료 시간 (초)
    style: str = "subtitle"     # hook, subtitle, caption, hashtag, emphasis, minimal
    position: str = "bottom"    # top, center, bottom, top_left, bottom_right, etc.
    custom_x: Optional[int] = None  # 커스텀 X 좌표
    custom_y: Optional[int] = None  # 커스텀 Y 좌표
    fontsize: Optional[int] = None  # 스타일 오버라이드
    fontcolor: Optional[str] = None
    animation: Optional[str] = None  # fade, pop, slide, none


@dataclass
class OverlayConfig:
    """전체 오버레이 설정"""
    overlays: List[TextOverlay]
    font_path: Optional[str] = None
    output_suffix: str = "_text"


# =============================================================================
# Font Detection
# =============================================================================

def get_system_font() -> str:
    """시스템에 맞는 한글 폰트 경로 반환"""
    import platform
    system = platform.system().lower()

    if system == "darwin":  # macOS
        fonts = FONT_PATHS["macos"]
    else:  # Linux
        fonts = FONT_PATHS["linux"]

    # 우선순위: noto_bold > noto > bold > default
    for key in ["noto_bold", "noto", "bold", "default"]:
        if key in fonts and os.path.exists(fonts[key]):
            return fonts[key]

    # 폴백: 시스템 기본
    return fonts.get("default", "")


def check_font_exists(font_path: str) -> bool:
    """폰트 파일 존재 확인"""
    return os.path.exists(font_path)


# =============================================================================
# FFmpeg Filter Generation
# =============================================================================

def escape_text_for_ffmpeg(text: str) -> str:
    """FFmpeg drawtext용 텍스트 이스케이프"""
    # 특수 문자 이스케이프
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\\'")
    text = text.replace(":", "\\:")
    text = text.replace("%", "\\%")
    return text


def generate_fade_expression(start: float, end: float, fade_duration: float = 0.3) -> str:
    """페이드 인/아웃 알파 표현식 생성"""
    fade_in_end = start + fade_duration
    fade_out_start = end - fade_duration

    expr = (
        f"if(lt(t,{start}),0,"
        f"if(lt(t,{fade_in_end}),(t-{start})/{fade_duration},"
        f"if(lt(t,{fade_out_start}),1,"
        f"if(lt(t,{end}),({end}-t)/{fade_duration},0))))"
    )
    return expr


def generate_pop_expression(start: float, end: float) -> str:
    """팝 애니메이션 (스케일 효과는 복잡해서 알파로 대체)"""
    # 빠른 페이드인 + 일반 페이드아웃
    fade_in_duration = 0.15
    fade_out_duration = 0.3
    fade_in_end = start + fade_in_duration
    fade_out_start = end - fade_out_duration

    expr = (
        f"if(lt(t,{start}),0,"
        f"if(lt(t,{fade_in_end}),(t-{start})/{fade_in_duration},"
        f"if(lt(t,{fade_out_start}),1,"
        f"if(lt(t,{end}),({end}-t)/{fade_out_duration},0))))"
    )
    return expr


def generate_slide_expression(start: float, end: float, direction: str = "up") -> str:
    """슬라이드 애니메이션 Y 좌표 표현식"""
    slide_duration = 0.3
    slide_end = start + slide_duration

    if direction == "up":
        # 아래에서 위로
        expr = f"if(lt(t,{start}),h,if(lt(t,{slide_end}),h-(h*0.12)*((t-{start})/{slide_duration}),h*0.88))"
    else:
        # 위에서 아래로
        expr = f"if(lt(t,{start}),0,if(lt(t,{slide_end}),(h*0.08)*((t-{start})/{slide_duration}),h*0.08))"

    return expr


def create_drawtext_filter(overlay: TextOverlay, font_path: str) -> str:
    """단일 텍스트 오버레이용 drawtext 필터 생성"""
    # 스타일 프리셋 가져오기
    style = STYLE_PRESETS.get(overlay.style, STYLE_PRESETS["subtitle"]).copy()

    # 오버라이드 적용
    if overlay.fontsize:
        style["fontsize"] = overlay.fontsize
    if overlay.fontcolor:
        style["fontcolor"] = overlay.fontcolor

    # 텍스트 이스케이프
    escaped_text = escape_text_for_ffmpeg(overlay.text)

    # 위치 계산
    if overlay.custom_x is not None and overlay.custom_y is not None:
        position = f"x={overlay.custom_x}:y={overlay.custom_y}"
    else:
        position = POSITION_PRESETS.get(overlay.position, POSITION_PRESETS["bottom"])

    # 애니메이션 선택
    animation = overlay.animation or style.get("animation", "fade")

    # 알파 표현식
    if animation == "pop":
        alpha_expr = generate_pop_expression(overlay.start_time, overlay.end_time)
    elif animation == "none":
        alpha_expr = f"if(between(t,{overlay.start_time},{overlay.end_time}),1,0)"
    else:  # fade (기본)
        alpha_expr = generate_fade_expression(overlay.start_time, overlay.end_time)

    # drawtext 필터 조합
    filter_parts = [
        f"drawtext=text='{escaped_text}'",
        f"fontfile='{font_path}'",
        f"fontsize={style['fontsize']}",
        f"fontcolor={style['fontcolor']}",
    ]

    # 테두리 (borderw > 0인 경우만)
    if style.get("borderw", 0) > 0:
        filter_parts.append(f"borderw={style['borderw']}")
        filter_parts.append(f"bordercolor={style['bordercolor']}")

    # 그림자
    if style.get("shadowx", 0) > 0:
        filter_parts.append(f"shadowx={style['shadowx']}")
        filter_parts.append(f"shadowy={style['shadowy']}")
        filter_parts.append(f"shadowcolor={style['shadowcolor']}")

    # 위치
    filter_parts.append(position)

    # 알파 (애니메이션)
    filter_parts.append(f"alpha='{alpha_expr}'")

    # enable 조건 (약간의 마진)
    margin = 0.5
    filter_parts.append(f"enable='between(t,{overlay.start_time - margin},{overlay.end_time + margin})'")

    return ":".join(filter_parts)


def create_filter_complex(overlays: List[TextOverlay], font_path: str) -> str:
    """여러 텍스트 오버레이를 위한 filter_complex 생성"""
    filters = []
    for overlay in overlays:
        filter_str = create_drawtext_filter(overlay, font_path)
        filters.append(filter_str)

    return ",".join(filters)


# =============================================================================
# Video Processing
# =============================================================================

def apply_text_overlays(
    video_path: str,
    overlays: List[TextOverlay],
    output_path: str,
    font_path: Optional[str] = None
) -> Optional[str]:
    """영상에 텍스트 오버레이 적용"""

    if not os.path.exists(video_path):
        print(f"❌ 영상 파일을 찾을 수 없습니다: {video_path}")
        return None

    # 폰트 경로 확인
    if font_path is None:
        font_path = get_system_font()

    if not check_font_exists(font_path):
        print(f"⚠️ 폰트를 찾을 수 없습니다: {font_path}")
        print("   시스템 기본 폰트를 사용합니다.")
        font_path = ""

    if not overlays:
        print("⚠️ 적용할 텍스트 오버레이가 없습니다.")
        # 원본 복사
        subprocess.run(["cp", video_path, output_path], check=True)
        return output_path

    print(f"🔤 텍스트 오버레이 적용 중... ({len(overlays)}개)")

    # 필터 생성
    filter_complex = create_filter_complex(overlays, font_path)

    # FFmpeg 실행
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", filter_complex,
        "-c:a", "copy",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        output_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"✅ 텍스트 오버레이 완료: {output_path}")
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg 오류: {e.stderr[:500]}")
        return None


def get_video_duration(video_path: str) -> float:
    """영상 길이 가져오기"""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except:
        return 60.0  # 기본값


# =============================================================================
# Preset Generators
# =============================================================================

def generate_shorts_overlays(
    hook_text: str,
    hashtags: List[str],
    duration: float = 60.0,
    subtitle_texts: Optional[List[tuple]] = None
) -> List[TextOverlay]:
    """Shorts 영상용 기본 오버레이 세트 생성

    Args:
        hook_text: 훅 텍스트 (첫 3초)
        hashtags: 해시태그 목록
        duration: 영상 길이
        subtitle_texts: [(시작, 끝, 텍스트), ...] 자막 목록
    """
    overlays = []

    # 1. 훅 텍스트 (0.5~3초)
    if hook_text:
        overlays.append(TextOverlay(
            text=hook_text,
            start_time=0.3,
            end_time=3.0,
            style="hook",
            position="center",
            animation="pop"
        ))

    # 2. 자막 (옵션)
    if subtitle_texts:
        for start, end, text in subtitle_texts:
            overlays.append(TextOverlay(
                text=text,
                start_time=start,
                end_time=end,
                style="subtitle",
                position="bottom",
                animation="fade"
            ))

    # 3. 해시태그 (마지막 4초)
    if hashtags:
        hashtag_text = " ".join(hashtags[:4])  # 최대 4개
        overlays.append(TextOverlay(
            text=hashtag_text,
            start_time=duration - 4.0,
            end_time=duration - 0.3,
            style="hashtag",
            position="bottom_left",
            animation="slide"
        ))

    return overlays


# =============================================================================
# CLI Interface
# =============================================================================

def run_test():
    """테스트 실행"""
    print("=" * 60)
    print("🧪 TEXT OVERLAY TEST")
    print("=" * 60)

    # 테스트 오버레이 생성
    overlays = generate_shorts_overlays(
        hook_text="헐, AI 고양이 실화냐?",
        hashtags=["#shorts", "#AI", "#고양이", "#유튜브"],
        duration=60.0,
        subtitle_texts=[
            (5.0, 10.0, "AI가 그린 고양이 사진인데..."),
            (12.0, 18.0, "진짜 실제 고양이 같지 않아요?"),
            (25.0, 32.0, "이게 가능하다니 충격"),
        ]
    )

    print(f"\n📝 생성된 오버레이: {len(overlays)}개\n")

    for i, overlay in enumerate(overlays, 1):
        print(f"{i}. [{overlay.style}] {overlay.start_time:.1f}s ~ {overlay.end_time:.1f}s")
        print(f"   텍스트: {overlay.text}")
        print(f"   위치: {overlay.position}, 애니메이션: {overlay.animation}")
        print()

    # 폰트 확인
    font = get_system_font()
    print(f"🔤 시스템 폰트: {font}")
    print(f"   존재: {'✅' if check_font_exists(font) else '❌'}")

    # 필터 미리보기
    print("\n📋 FFmpeg 필터 미리보기 (첫 번째 오버레이):")
    if overlays:
        filter_str = create_drawtext_filter(overlays[0], font)
        # 줄바꿈으로 보기 좋게
        print("   " + filter_str.replace(":", ":\n   "))

    print("\n" + "=" * 60)
    print("✅ Test complete")
    print("\n사용 예시:")
    print("  python3 text_overlay.py --video input.mp4 --text '헐 실화냐' --style hook")


def main():
    parser = argparse.ArgumentParser(
        description="영상 텍스트 오버레이 도구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
스타일 옵션:
  hook      - 첫 3초 훅 (크고 강렬한 노란색)
  subtitle  - 자막 (하단, 흰색)
  caption   - 캡션 (상단, 정보 표시)
  hashtag   - 해시태그 (하단 좌측, 시안색)
  emphasis  - 강조 (빨간색, 중앙)
  minimal   - 미니멀 (감성형 영상용)

위치 옵션:
  top, top_left, top_right
  center, center_left, center_right
  bottom, bottom_left, bottom_right

예시:
  # 훅 텍스트 추가
  python3 text_overlay.py --video input.mp4 --text "헐 실화냐?" --style hook

  # JSON 설정 파일 사용
  python3 text_overlay.py --video input.mp4 --config overlays.json

  # 여러 옵션 지정
  python3 text_overlay.py --video input.mp4 --text "자막입니다" \\
    --style subtitle --start 5 --end 10 --position bottom
"""
    )

    parser.add_argument("--video", "-v", help="입력 영상 파일")
    parser.add_argument("--output", "-o", help="출력 영상 파일")
    parser.add_argument("--text", "-t", help="오버레이 텍스트")
    parser.add_argument("--style", "-s", default="subtitle",
                        choices=list(STYLE_PRESETS.keys()),
                        help="텍스트 스타일 (기본: subtitle)")
    parser.add_argument("--position", "-p", default="bottom",
                        choices=list(POSITION_PRESETS.keys()),
                        help="텍스트 위치 (기본: bottom)")
    parser.add_argument("--start", type=float, default=0.0,
                        help="시작 시간 (초)")
    parser.add_argument("--end", type=float, help="종료 시간 (초)")
    parser.add_argument("--config", "-c", help="JSON 설정 파일")
    parser.add_argument("--font", "-f", help="폰트 파일 경로")
    parser.add_argument("--test", action="store_true", help="테스트 실행")
    parser.add_argument("--list-styles", action="store_true", help="스타일 목록 출력")

    args = parser.parse_args()

    if args.list_styles:
        print("\n📝 사용 가능한 스타일:\n")
        for name, preset in STYLE_PRESETS.items():
            print(f"  {name:12} - {preset['description']}")
        return

    if args.test:
        run_test()
        return

    if not args.video:
        parser.print_help()
        return

    # 출력 경로
    if args.output:
        output_path = args.output
    else:
        base, ext = os.path.splitext(args.video)
        output_path = f"{base}_text{ext}"

    # 오버레이 목록 구성
    overlays = []

    if args.config:
        # JSON 설정 파일에서 로드
        with open(args.config, "r", encoding="utf-8") as f:
            config_data = json.load(f)

        for item in config_data.get("overlays", []):
            overlays.append(TextOverlay(**item))
    elif args.text:
        # 커맨드라인 인자로 단일 오버레이
        duration = get_video_duration(args.video)
        end_time = args.end if args.end else min(args.start + 5.0, duration)

        overlays.append(TextOverlay(
            text=args.text,
            start_time=args.start,
            end_time=end_time,
            style=args.style,
            position=args.position
        ))
    else:
        print("❌ --text 또는 --config 옵션이 필요합니다.")
        return

    # 적용
    result = apply_text_overlays(
        video_path=args.video,
        overlays=overlays,
        output_path=output_path,
        font_path=args.font
    )

    if result:
        print(f"\n📹 결과: {result}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
