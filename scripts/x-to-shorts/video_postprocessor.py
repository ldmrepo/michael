#!/usr/bin/env python3
"""
영상 후처리 파이프라인

Veo 3.1로 생성된 영상에 텍스트 오버레이를 추가하는 후처리 단계입니다.

워크플로우:
1. 텍스트 없는 영상 입력
2. 텍스트 오버레이 설정 로드
3. FFmpeg로 텍스트 합성
4. 최종 영상 출력

Usage:
    python3 video_postprocessor.py --video input.mp4 --plan project_plan.json
    python3 video_postprocessor.py --video input.mp4 --overlays overlays.json
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

# Import local modules
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from text_overlay import TextOverlay, apply_text_overlays, get_video_duration


# =============================================================================
# Post-processing Pipeline
# =============================================================================

def load_overlays_from_plan(plan_path: str) -> List[TextOverlay]:
    """프로젝트 플랜에서 텍스트 오버레이 로드"""
    with open(plan_path, "r", encoding="utf-8") as f:
        plan = json.load(f)

    overlays = []
    for item in plan.get("text_overlays", []):
        overlays.append(TextOverlay(**item))

    return overlays


def load_overlays_from_json(json_path: str) -> List[TextOverlay]:
    """JSON 파일에서 텍스트 오버레이 로드"""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    overlays = []

    # overlays 키가 있으면 그 안의 데이터 사용
    if "overlays" in data:
        items = data["overlays"]
    elif isinstance(data, list):
        items = data
    else:
        items = []

    for item in items:
        overlays.append(TextOverlay(**item))

    return overlays


def postprocess_video(
    video_path: str,
    output_path: Optional[str] = None,
    plan_path: Optional[str] = None,
    overlays_path: Optional[str] = None,
    overlays: Optional[List[TextOverlay]] = None,
    font_path: Optional[str] = None
) -> Optional[str]:
    """영상 후처리 실행

    Args:
        video_path: 입력 영상 경로
        output_path: 출력 영상 경로 (없으면 자동 생성)
        plan_path: 프로젝트 플랜 JSON 경로
        overlays_path: 오버레이 설정 JSON 경로
        overlays: TextOverlay 객체 리스트 (직접 전달)
        font_path: 폰트 파일 경로

    Returns:
        출력 영상 경로 또는 None
    """
    print("=" * 60)
    print("🎬 영상 후처리 파이프라인")
    print("=" * 60)

    if not os.path.exists(video_path):
        print(f"❌ 영상 파일을 찾을 수 없습니다: {video_path}")
        return None

    # 오버레이 로드
    text_overlays = overlays or []

    if plan_path and os.path.exists(plan_path):
        print(f"📋 프로젝트 플랜에서 오버레이 로드: {plan_path}")
        text_overlays = load_overlays_from_plan(plan_path)
    elif overlays_path and os.path.exists(overlays_path):
        print(f"📋 오버레이 설정 로드: {overlays_path}")
        text_overlays = load_overlays_from_json(overlays_path)

    if not text_overlays:
        print("⚠️ 적용할 텍스트 오버레이가 없습니다.")
        print("   원본 영상을 그대로 사용합니다.")
        return video_path

    print(f"\n📊 영상 정보:")
    duration = get_video_duration(video_path)
    print(f"   길이: {duration:.1f}초")
    print(f"   오버레이: {len(text_overlays)}개")

    # 오버레이 목록 표시
    print(f"\n🔤 텍스트 오버레이:")
    for i, overlay in enumerate(text_overlays, 1):
        print(f"   {i}. [{overlay.style}] {overlay.start_time:.1f}s ~ {overlay.end_time:.1f}s")
        print(f"      \"{overlay.text[:40]}{'...' if len(overlay.text) > 40 else ''}\"")

    # 출력 경로 설정
    if output_path is None:
        base, ext = os.path.splitext(video_path)
        output_path = f"{base}_final{ext}"

    # 텍스트 오버레이 적용
    print(f"\n🔧 FFmpeg 처리 중...")
    result = apply_text_overlays(
        video_path=video_path,
        overlays=text_overlays,
        output_path=output_path,
        font_path=font_path
    )

    if result:
        print(f"\n✅ 후처리 완료!")
        print(f"   입력: {video_path}")
        print(f"   출력: {result}")

        # 파일 크기 확인
        size_mb = os.path.getsize(result) / (1024 * 1024)
        print(f"   크기: {size_mb:.2f} MB")

    return result


def create_sample_overlays_json(output_path: str, duration: float = 60.0):
    """샘플 오버레이 설정 파일 생성"""
    sample = {
        "description": "YouTube Shorts 텍스트 오버레이 설정 예시",
        "overlays": [
            {
                "text": "헐, 이거 실화?",
                "start_time": 0.5,
                "end_time": 3.0,
                "style": "hook",
                "position": "center",
                "animation": "pop"
            },
            {
                "text": "놀라운 사실을 알려드립니다",
                "start_time": 5.0,
                "end_time": 10.0,
                "style": "subtitle",
                "position": "bottom",
                "animation": "fade"
            },
            {
                "text": "#shorts #유튜브쇼츠 #trending",
                "start_time": duration - 4.0,
                "end_time": duration - 0.5,
                "style": "hashtag",
                "position": "bottom_left",
                "animation": "slide"
            }
        ]
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sample, f, ensure_ascii=False, indent=2)

    print(f"✅ 샘플 오버레이 설정 생성됨: {output_path}")


# =============================================================================
# Batch Processing
# =============================================================================

def batch_postprocess(
    video_dir: str,
    plan_path: Optional[str] = None,
    output_dir: Optional[str] = None
) -> List[str]:
    """여러 영상 일괄 후처리

    Args:
        video_dir: 영상 파일들이 있는 디렉토리
        plan_path: 공통 프로젝트 플랜 경로
        output_dir: 출력 디렉토리 (없으면 video_dir 사용)

    Returns:
        처리된 영상 경로 목록
    """
    results = []
    video_dir = Path(video_dir)

    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        output_path = video_dir

    # 영상 파일 찾기
    video_files = list(video_dir.glob("*.mp4"))

    if not video_files:
        print(f"⚠️ {video_dir}에서 영상 파일을 찾을 수 없습니다.")
        return results

    print(f"📁 {len(video_files)}개 영상 발견")

    for video_file in video_files:
        # final_ 접미사가 이미 있으면 건너뛰기
        if "_final" in video_file.stem or "_text" in video_file.stem:
            continue

        output_file = output_path / f"{video_file.stem}_final{video_file.suffix}"

        result = postprocess_video(
            video_path=str(video_file),
            output_path=str(output_file),
            plan_path=plan_path
        )

        if result:
            results.append(result)

    return results


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="영상 후처리 파이프라인 (텍스트 오버레이)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 프로젝트 플랜에서 오버레이 적용
  python3 video_postprocessor.py --video final.mp4 --plan project_plan.json

  # 오버레이 설정 파일 사용
  python3 video_postprocessor.py --video final.mp4 --overlays overlays.json

  # 샘플 오버레이 설정 생성
  python3 video_postprocessor.py --create-sample sample_overlays.json

  # 일괄 처리
  python3 video_postprocessor.py --batch /tmp/shorts --plan project_plan.json
"""
    )

    parser.add_argument("--video", "-v", help="입력 영상 파일")
    parser.add_argument("--output", "-o", help="출력 영상 파일")
    parser.add_argument("--plan", "-p", help="프로젝트 플랜 JSON")
    parser.add_argument("--overlays", help="오버레이 설정 JSON")
    parser.add_argument("--font", "-f", help="폰트 파일 경로")
    parser.add_argument("--batch", "-b", help="일괄 처리할 디렉토리")
    parser.add_argument("--create-sample", help="샘플 오버레이 설정 생성")
    parser.add_argument("--output-dir", help="일괄 처리 출력 디렉토리")

    args = parser.parse_args()

    if args.create_sample:
        create_sample_overlays_json(args.create_sample)
        return

    if args.batch:
        results = batch_postprocess(
            video_dir=args.batch,
            plan_path=args.plan,
            output_dir=args.output_dir
        )
        print(f"\n✅ {len(results)}개 영상 처리 완료")
        return

    if not args.video:
        parser.print_help()
        return

    result = postprocess_video(
        video_path=args.video,
        output_path=args.output,
        plan_path=args.plan,
        overlays_path=args.overlays,
        font_path=args.font
    )

    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
