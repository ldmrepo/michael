#!/usr/bin/env python3
"""
AI 아트 채널 전체 파이프라인

X에서 AI 아트 수집 → 분석 → 영상 생성 → (선택) 업로드

Usage:
    # 테스트 실행
    python3 generate_ai_art_shorts.py --test

    # JSON 파일에서 영상 생성
    python3 generate_ai_art_shorts.py --input tweets.json --auto-generate

    # 드라이런 (분석만)
    python3 generate_ai_art_shorts.py --query "midjourney min_faves:1000" --dry-run
"""

import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional, Tuple

# Local imports
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent / "x-to-shorts"))

from config import (
    CHANNEL_NAME,
    VIDEO_FORMAT,
    VIDEO_MODES,
    VIRAL_THRESHOLDS,
    DEFAULT_HASHTAGS,
    OUTPUT_DIR,
)

from art_collector import (
    AIArtData,
    AIArtAnalysis,
    parse_ai_art_from_json,
    parse_ai_art_from_file,
    analyze_ai_art_batch,
    filter_by_threshold,
    display_results,
    save_results,
    collect_ai_art_from_x,
)

from image_video_maker import (
    create_ai_art_video,
    create_single_image_video,
)


# =============================================================================
# Pipeline Functions
# =============================================================================

def determine_video_mode(viral_score: int) -> str:
    """바이럴 점수에 따른 영상 생성 모드 결정"""
    if viral_score >= VIDEO_MODES["full_veo"]["min_score"]:
        return "full_veo"
    elif viral_score >= VIDEO_MODES["hybrid"]["min_score"]:
        return "hybrid"
    else:
        return "image_only"


def generate_video_for_art(
    art_data: AIArtData,
    analysis: AIArtAnalysis,
    output_dir: str,
    mode: str = "auto"
) -> Optional[str]:
    """AI 아트 데이터로 영상 생성

    Args:
        art_data: AI 아트 데이터
        analysis: 분석 결과
        output_dir: 출력 디렉토리
        mode: 생성 모드 (auto, image_only, hybrid, full_veo)

    Returns:
        생성된 영상 경로 또는 None
    """
    os.makedirs(output_dir, exist_ok=True)

    # 모드 자동 결정
    if mode == "auto":
        mode = determine_video_mode(analysis.viral_score)

    print(f"\n🎬 영상 생성 모드: {mode}")
    print(f"   예상 비용: ${VIDEO_MODES[mode]['cost_per_video']:.2f}")

    # 이미지 경로 확인
    image_paths = art_data.media_urls if art_data.media_urls else art_data.media

    if not image_paths:
        print("⚠️ 이미지가 없습니다. 텍스트 기반 영상으로 대체...")
        # TODO: 텍스트만으로 영상 생성하는 로직 추가 가능
        return None

    # 훅 텍스트
    hook_text = analysis.hook_suggestion or f"AI가 만든 {art_data.art_style} 실화냐?"

    # 해시태그
    hashtags = DEFAULT_HASHTAGS + [f"#{art_data.ai_tool}"]

    timestamp = int(time.time())
    output_path = os.path.join(output_dir, f"ai_art_{timestamp}.mp4")

    if mode == "image_only":
        # FFmpeg만 사용 (비용 $0)
        if len(image_paths) == 1:
            return create_single_image_video(
                image_path=image_paths[0],
                output_path=output_path,
                hook_text=hook_text,
                hashtags=hashtags,
                duration=VIDEO_FORMAT["duration_seconds"]
            )
        else:
            return create_ai_art_video(
                image_paths=image_paths,
                output_path=output_path,
                hook_text=hook_text,
                hashtags=hashtags,
                total_duration=VIDEO_FORMAT["duration_seconds"]
            )

    elif mode in ("hybrid", "full_veo"):
        # Veo 3.1 사용 (비용 발생)
        # TODO: Veo API 연동 구현
        print("⚠️ Veo 3.1 모드는 아직 구현 중입니다. image_only로 대체합니다.")
        return create_single_image_video(
            image_path=image_paths[0] if image_paths else None,
            output_path=output_path,
            hook_text=hook_text,
            hashtags=hashtags,
            duration=VIDEO_FORMAT["duration_seconds"]
        )

    return None


def generate_youtube_metadata(
    art_data: AIArtData,
    analysis: AIArtAnalysis
) -> dict:
    """YouTube 업로드용 메타데이터 생성"""
    # 제목 생성
    style_names = {
        "photorealistic": "초현실적인",
        "anime": "애니메이션 스타일",
        "fantasy": "판타지",
        "cyberpunk": "사이버펑크",
        "portrait": "인물화",
        "landscape": "풍경",
        "cute": "귀여운",
        "surreal": "초현실적인",
        "unknown": "놀라운",
    }
    style = style_names.get(art_data.art_style, "놀라운")

    tool_names = {
        "midjourney": "미드저니",
        "stable_diffusion": "SD",
        "dalle": "달리",
        "flux": "Flux",
        "unknown": "AI",
    }
    tool = tool_names.get(art_data.ai_tool, "AI")

    title = f"{tool}로 만든 {style} 작품 🤖 #shorts"

    # 설명 생성
    description = f"""
{analysis.hook_suggestion}

🎨 AI 도구: {art_data.ai_tool.upper()}
🖼️ 스타일: {art_data.art_style}
📊 바이럴 점수: {analysis.viral_score}/100

원본 출처: {art_data.url or art_data.author}

{' '.join(DEFAULT_HASHTAGS)}

---
{CHANNEL_NAME} - AI가 만든 놀라운 작품들
구독하면 최신 AI 아트 트렌드를 놓치지 않아요! 🔔
""".strip()

    # 태그
    tags = [
        "AI art", "AI 아트", art_data.ai_tool, art_data.art_style,
        "인공지능", "미드저니", "shorts", "쇼츠", CHANNEL_NAME
    ]

    return {
        "title": title,
        "description": description,
        "tags": tags,
        "category": "22",  # People & Blogs
        "privacy": "public",
        "shorts": True
    }


# =============================================================================
# Main Pipeline
# =============================================================================

def run_pipeline(
    query: str = "",
    input_file: str = "",
    input_json: str = "",
    count: int = 5,
    output_dir: str = OUTPUT_DIR,
    auto_generate: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
    threshold: str = "recommended",
    video_mode: str = "auto"
) -> dict:
    """
    전체 파이프라인 실행

    Args:
        query: X 검색 쿼리
        input_file: 트윗 JSON 파일 경로
        input_json: 트윗 JSON 문자열
        count: 분석할 트윗 수
        output_dir: 출력 디렉토리
        auto_generate: 자동 영상 생성 여부
        dry_run: 드라이런 (분석만)
        verbose: 상세 출력
        threshold: 바이럴 임계값
        video_mode: 영상 생성 모드

    Returns:
        결과 딕셔너리
    """
    print("=" * 60)
    print(f"🎨 {CHANNEL_NAME} - AI 아트 쇼츠 생성 파이프라인")
    print("=" * 60)

    timestamp = int(time.time())
    run_output_dir = os.path.join(output_dir, f"run_{timestamp}")
    os.makedirs(run_output_dir, exist_ok=True)

    # 1. AI 아트 수집
    art_list = []

    if input_file:
        print(f"\n[1/4] 📥 파일에서 AI 아트 로드: {input_file}")
        art_list = parse_ai_art_from_file(input_file)
    elif input_json:
        print(f"\n[1/4] 📥 JSON에서 AI 아트 파싱")
        art_list = parse_ai_art_from_json(input_json)
    elif query:
        print(f"\n[1/4] 🔍 X 검색: {query}")
        art_list = collect_ai_art_from_x(query, count)

        if not art_list:
            print()
            print("⚠️  X 검색을 위해서는 Playwright MCP 연동이 필요합니다.")
            print()
            print("사용 방법:")
            print("  1. Claude에게 X 검색 요청")
            print("  2. 결과를 JSON으로 저장")
            print("  3. 이 스크립트에 --input 옵션으로 전달")
            print()
            print("또는 샘플 데이터로 테스트:")
            print(f"  python3 {__file__} --test")
            return {"success": False, "error": "No art collected"}

    if not art_list:
        print("❌ 분석할 AI 아트가 없습니다.")
        return {"success": False, "error": "No art data"}

    art_list = art_list[:count]
    print(f"   {len(art_list)}개 AI 아트 로드됨")

    # 2. 분석
    print(f"\n[2/4] 📊 바이럴 분석 중...")
    results = analyze_ai_art_batch(art_list)

    # 필터링
    filtered = filter_by_threshold(results, threshold)
    print(f"   {threshold} 기준 통과: {len(filtered)}/{len(results)}")

    # 결과 표시
    display_results(filtered, verbose)

    if dry_run:
        print("\n🏁 드라이런 완료. 영상 생성 없음.")
        return {
            "success": True,
            "analyzed_count": len(results),
            "filtered_count": len(filtered),
            "dry_run": True
        }

    # 3. 결과 저장
    print(f"\n[3/4] 💾 분석 결과 저장 중...")
    results_path = os.path.join(run_output_dir, "analysis.json")
    save_results(filtered, results_path)

    # 4. 영상 생성 (선택)
    if auto_generate and filtered:
        print(f"\n[4/4] 🎬 영상 자동 생성 중...")

        # 가장 점수 높은 AI 아트로 영상 생성
        top_art, top_analysis = filtered[0]

        video_output_dir = os.path.join(run_output_dir, "video")
        video_path = generate_video_for_art(
            art_data=top_art,
            analysis=top_analysis,
            output_dir=video_output_dir,
            mode=video_mode
        )

        # YouTube 메타데이터 생성
        metadata = generate_youtube_metadata(top_art, top_analysis)
        metadata_path = os.path.join(video_output_dir, "youtube_metadata.json")
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        return {
            "success": True,
            "analyzed_count": len(results),
            "filtered_count": len(filtered),
            "analysis_path": results_path,
            "video_path": video_path,
            "metadata_path": metadata_path,
            "top_art": asdict(top_art),
            "top_analysis": asdict(top_analysis)
        }

    return {
        "success": True,
        "analyzed_count": len(results),
        "filtered_count": len(filtered),
        "analysis_path": results_path,
        "output_dir": run_output_dir
    }


def run_test():
    """테스트 실행"""
    print("=" * 60)
    print("🧪 AI ART SHORTS PIPELINE TEST")
    print("=" * 60)

    # 샘플 AI 아트 트윗
    sample_tweets = [
        {
            "tweet_id": "1",
            "text": "미드저니 v6로 만든 고양이인데... 실화냐? 진짜 사진 같음 ㅋㅋㅋ #midjourney #AI아트",
            "author": "@ai_artist1",
            "retweets": 8000,
            "likes": 25000,
            "replies": 500,
            "media": [],  # 테스트용으로 이미지 없음
            "hashtags": ["#midjourney", "#AI아트"],
            "url": "https://x.com/ai_artist1/status/1"
        },
        {
            "tweet_id": "2",
            "text": "Stable Diffusion으로 지브리 스타일 풍경 만들어봤습니다",
            "author": "@sd_creator",
            "retweets": 5000,
            "likes": 18000,
            "replies": 300,
            "media": [],
            "hashtags": ["#StableDiffusion", "#지브리"],
            "url": "https://x.com/sd_creator/status/2"
        },
        {
            "tweet_id": "3",
            "text": "DALL-E 3로 사이버펑크 도시 만들어봄. 네온 조명 미쳤다",
            "author": "@dalle_fan",
            "retweets": 3500,
            "likes": 12000,
            "replies": 200,
            "media": [],
            "hashtags": ["#DALLE", "#사이버펑크"],
            "url": "https://x.com/dalle_fan/status/3"
        },
    ]

    input_json = json.dumps(sample_tweets, ensure_ascii=False)

    result = run_pipeline(
        input_json=input_json,
        count=5,
        output_dir="/tmp/ai-art-shorts-test",
        verbose=True,
        dry_run=True,  # 테스트에서는 영상 생성 안함
        threshold="consider"  # 낮은 임계값으로 테스트
    )

    print()
    print("=" * 60)
    print("✅ 파이프라인 테스트 완료")
    print(f"   분석된 AI 아트: {result.get('analyzed_count', 0)}개")
    print(f"   필터 통과: {result.get('filtered_count', 0)}개")
    print("=" * 60)

    return result


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description=f"{CHANNEL_NAME} - AI 아트 쇼츠 생성 파이프라인",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 테스트 실행
  python3 generate_ai_art_shorts.py --test

  # JSON 파일에서 분석
  python3 generate_ai_art_shorts.py --input tweets.json --verbose

  # 자동 영상 생성
  python3 generate_ai_art_shorts.py --input tweets.json --auto-generate

  # 드라이런 (분석만)
  python3 generate_ai_art_shorts.py --query "midjourney min_faves:1000" --dry-run

  # 비용 최적화 모드
  python3 generate_ai_art_shorts.py --input tweets.json --auto-generate --video-mode image_only
"""
    )

    parser.add_argument("--test", "-t", action="store_true", help="테스트 실행")
    parser.add_argument("--input", "-i", dest="input_file", help="입력 JSON 파일")
    parser.add_argument("--query", "-q", help="X 검색 쿼리")
    parser.add_argument("--count", "-c", type=int, default=5, help="분석할 트윗 수")
    parser.add_argument("--output", "-o", default=OUTPUT_DIR, help="출력 디렉토리")
    parser.add_argument("--auto-generate", "-a", action="store_true",
                        help="가장 높은 점수의 AI 아트로 자동 영상 생성")
    parser.add_argument("--dry-run", "-d", action="store_true", help="드라이런 (분석만)")
    parser.add_argument("--verbose", "-v", action="store_true", help="상세 출력")
    parser.add_argument("--threshold", choices=list(VIRAL_THRESHOLDS.keys()),
                        default="recommended", help="바이럴 임계값")
    parser.add_argument("--video-mode", choices=["auto", "image_only", "hybrid", "full_veo"],
                        default="auto", help="영상 생성 모드")
    parser.add_argument("--json", action="store_true", help="JSON 형식으로 출력")

    args = parser.parse_args()

    if args.test:
        run_test()
        return

    if not args.query and not args.input_file:
        print("⚠️  --query 또는 --input 옵션이 필요합니다.")
        print("   테스트 실행: python3 generate_ai_art_shorts.py --test")
        print()
        parser.print_help()
        sys.exit(1)

    result = run_pipeline(
        query=args.query or "",
        input_file=args.input_file or "",
        count=args.count,
        output_dir=args.output,
        auto_generate=args.auto_generate,
        dry_run=args.dry_run,
        verbose=args.verbose,
        threshold=args.threshold,
        video_mode=args.video_mode
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
