#!/usr/bin/env python3
"""
X(Twitter) 트렌드 기반 YouTube Shorts 생성 파이프라인

X에서 바이럴 트윗을 수집 → 분석 → Shorts 아이디어 생성 → (선택) 영상 생성

Usage:
    # 아이디어만 생성
    python3 generate_from_x.py --query "lang:ko min_retweets:1000" --count 5

    # 영상까지 자동 생성
    python3 generate_from_x.py --query "lang:ko min_retweets:1000" --auto-generate

    # 드라이런 (분석만)
    python3 generate_from_x.py --query "lang:ko min_retweets:500" --dry-run
"""

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

# Import local modules
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from viral_analyzer import TweetData, analyze_tweet
from idea_transformer import ShortsIdea, ProjectPlan, transform_to_idea, transform_to_project_plan
from video_postprocessor import postprocess_video
from text_overlay import TextOverlay

# agentic_video.py path
YOUTUBE_SHORTS_DIR = SCRIPT_DIR.parent / "youtube-shorts"


# =============================================================================
# X (Twitter) Data Collection (Placeholder for Playwright integration)
# =============================================================================

def collect_tweets_from_x(query: str, count: int = 5) -> List[TweetData]:
    """
    X에서 트윗 수집 (Playwright 기반 X 스킬 연동)

    실제 구현에서는 Playwright MCP를 통해 X 검색을 수행합니다.
    이 함수는 Claude Agent가 X 스킬을 호출하여 데이터를 수집할 때
    사용할 데이터 구조를 정의합니다.
    """
    print(f"🔍 X 검색: {query}")
    print(f"   (Playwright X 스킬 연동 필요)")
    print()

    # 실제 구현에서는 여기서 Playwright를 통해 X 검색을 수행
    # 현재는 샘플 데이터 반환

    # 검색 URL 생성 (참고용)
    search_url = f"https://x.com/search?q={quote(query)}&src=typed_query&f=live"
    print(f"   검색 URL: {search_url}")
    print()

    return []


def parse_tweets_from_json(json_data: str) -> List[TweetData]:
    """JSON 문자열에서 트윗 데이터 파싱"""
    try:
        data = json.loads(json_data)
        if isinstance(data, list):
            return [TweetData(**t) for t in data]
        return []
    except (json.JSONDecodeError, TypeError):
        return []


def parse_tweets_from_file(file_path: str) -> List[TweetData]:
    """JSON 파일에서 트윗 데이터 로드"""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return [TweetData(**t) for t in data]
    return []


# =============================================================================
# Pipeline Functions
# =============================================================================

def analyze_and_transform(tweets: List[TweetData]) -> List[tuple]:
    """트윗 분석 및 아이디어 변환"""
    results = []

    for tweet in tweets:
        analysis = analyze_tweet(tweet)
        idea = transform_to_idea(tweet, analysis)
        plan = transform_to_project_plan(idea)
        results.append((tweet, analysis, idea, plan))

    # 바이럴 점수순 정렬
    results.sort(key=lambda x: x[1].viral_score, reverse=True)
    return results


def display_ideas(results: List[tuple], verbose: bool = False):
    """아이디어 목록 표시"""
    print()
    print("=" * 60)
    print("📊 바이럴 트윗 분석 결과")
    print("=" * 60)

    for i, (tweet, analysis, idea, plan) in enumerate(results, 1):
        template_names = {
            "reaction": "반응형",
            "tutorial": "정보형",
            "story": "스토리형",
            "aesthetic": "감성형"
        }

        print(f"\n{i}. [바이럴 점수: {analysis.viral_score}] {template_names.get(idea.template_type, idea.template_type)}")
        print(f"   원본: \"{tweet.text[:60]}{'...' if len(tweet.text) > 60 else ''}\"")
        print(f"   → 쇼츠 아이디어: {idea.brief}")

        if verbose:
            print(f"   훅: {idea.hook}")
            print(f"   구조: {idea.structure}")
            print(f"   핵심 비주얼: {idea.key_visual}")
            print(f"   오디오: {idea.audio_suggestion}")
            print(f"   해시태그: {' '.join(idea.hashtags[:5])}")
            print(f"   추천: {analysis.recommendation}")

    print()
    print("=" * 60)


def save_ideas(results: List[tuple], output_dir: str):
    """아이디어를 JSON 파일로 저장"""
    os.makedirs(output_dir, exist_ok=True)

    ideas_data = []
    for tweet, analysis, idea, plan in results:
        ideas_data.append({
            "source_tweet": {
                "id": tweet.tweet_id,
                "text": tweet.text,
                "author": tweet.author,
                "url": tweet.url,
                "retweets": tweet.retweets,
                "likes": tweet.likes,
            },
            "analysis": asdict(analysis),
            "idea": asdict(idea),
            "project_plan": {
                "brief": plan.brief,
                "viral_score": plan.viral_score,
                "template_type": plan.template_type,
                "continuity": plan.continuity,
                "beat_sheet": plan.beat_sheet,
                "shots": plan.shots,
                "text_overlays": plan.text_overlays,
                "text_safe_prompts": plan.text_safe_prompts
            }
        })

    output_path = os.path.join(output_dir, "ideas.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(ideas_data, f, ensure_ascii=False, indent=2)

    print(f"📄 아이디어 저장됨: {output_path}")
    return output_path


def generate_video(plan: ProjectPlan, output_dir: str, apply_text_overlay: bool = True, provider: Optional[str] = None) -> Optional[str]:
    """agentic_video.py를 사용하여 영상 생성 + 텍스트 오버레이 후처리

    Args:
        plan: ProjectPlan 객체
        output_dir: 출력 디렉토리
        apply_text_overlay: 텍스트 오버레이 적용 여부 (기본: True)
        provider: 영상 생성 프로바이더 ('veo' 또는 'sora')

    Returns:
        최종 영상 경로 또는 None
    """
    agentic_video_path = YOUTUBE_SHORTS_DIR / "agentic_video.py"

    if not agentic_video_path.exists():
        print(f"❌ agentic_video.py not found: {agentic_video_path}")
        return None

    # 프로젝트 플랜 저장 (텍스트 오버레이 포함)
    plan_path = os.path.join(output_dir, "project_plan.json")
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump({
            "brief": plan.brief,
            "continuity": plan.continuity,
            "beat_sheet": plan.beat_sheet,
            "shots": plan.shots,
            "text_overlays": plan.text_overlays,
            "text_safe_prompts": plan.text_safe_prompts
        }, f, ensure_ascii=False, indent=2)

    provider_name = (provider or "veo").upper()
    print(f"\n🎬 영상 생성 시작: {plan.brief}")
    print(f"   프로바이더: {provider_name}")
    print(f"   텍스트 안전 프롬프트: {'✅' if plan.text_safe_prompts else '❌'}")
    print(f"   텍스트 오버레이: {len(plan.text_overlays)}개 예정")

    raw_video_path = None

    try:
        # Step 1: AI 영상 생성 (텍스트 없음)
        print(f"\n[Step 1/2] 🎥 {provider_name} 영상 생성 (텍스트 없음)...")
        cmd = [
            "python3", str(agentic_video_path),
            "--brief", plan.brief,
            "--output", output_dir,
            "--style", "cinematic"
        ]
        if provider:
            cmd.extend(["--provider", provider])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10분 타임아웃
        )

        if result.returncode == 0:
            # 생성된 영상 찾기
            for f in os.listdir(output_dir):
                if f.startswith("final_") and f.endswith(".mp4"):
                    raw_video_path = os.path.join(output_dir, f)
                    print(f"   ✅ 원본 영상 생성 완료: {raw_video_path}")
                    break
        else:
            print(f"❌ 영상 생성 실패: {result.stderr[:200]}")
            return None

    except subprocess.TimeoutExpired:
        print("❌ 영상 생성 타임아웃")
        return None
    except Exception as e:
        print(f"❌ 영상 생성 오류: {e}")
        return None

    if not raw_video_path:
        print("❌ 생성된 영상을 찾을 수 없습니다.")
        return None

    # Step 2: 텍스트 오버레이 적용
    if apply_text_overlay and plan.text_overlays:
        print(f"\n[Step 2/2] 🔤 텍스트 오버레이 적용...")

        # 텍스트 오버레이 객체 변환
        overlays = [TextOverlay(**o) for o in plan.text_overlays]

        final_path = os.path.join(output_dir, f"final_with_text_{int(time.time())}.mp4")

        result = postprocess_video(
            video_path=raw_video_path,
            output_path=final_path,
            plan_path=plan_path
        )

        if result:
            print(f"   ✅ 최종 영상 완료: {result}")
            return result
        else:
            print(f"   ⚠️ 텍스트 오버레이 실패, 원본 영상 반환")
            return raw_video_path
    else:
        print(f"\n[Step 2/2] ⏭️ 텍스트 오버레이 스킵")
        return raw_video_path


# =============================================================================
# Main Pipeline
# =============================================================================

def run_pipeline(
    query: str = "",
    input_file: str = "",
    input_json: str = "",
    count: int = 5,
    output_dir: str = "/tmp/x-to-shorts",
    auto_generate: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
    provider: Optional[str] = None
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
        provider: 영상 생성 프로바이더 ('veo' 또는 'sora')

    Returns:
        결과 딕셔너리
    """
    print("=" * 60)
    print("🔥 X → SHORTS 아이디어 생성 파이프라인")
    print("=" * 60)

    timestamp = int(time.time())
    run_output_dir = os.path.join(output_dir, f"run_{timestamp}")
    os.makedirs(run_output_dir, exist_ok=True)

    # 1. 트윗 수집
    tweets = []

    if input_file:
        print(f"\n[1/3] 📥 파일에서 트윗 로드: {input_file}")
        tweets = parse_tweets_from_file(input_file)
    elif input_json:
        print(f"\n[1/3] 📥 JSON에서 트윗 파싱")
        tweets = parse_tweets_from_json(input_json)
    elif query:
        print(f"\n[1/3] 🔍 X 검색: {query}")
        tweets = collect_tweets_from_x(query, count)

        if not tweets:
            print()
            print("⚠️  실시간 X 검색을 위해서는 Playwright MCP를 통한 브라우저 자동화가 필요합니다.")
            print()
            print("사용 방법:")
            print("  1. Claude에게 X 검색 요청: \"X에서 'lang:ko min_retweets:1000' 검색해줘\"")
            print("  2. 결과를 JSON으로 저장")
            print("  3. 이 스크립트에 --input 옵션으로 전달")
            print()
            print("또는 샘플 데이터로 테스트:")
            print(f"  python3 {__file__} --test")
            print()

            return {"success": False, "error": "No tweets collected"}

    if not tweets:
        print("❌ 분석할 트윗이 없습니다.")
        return {"success": False, "error": "No tweets"}

    tweets = tweets[:count]
    print(f"   {len(tweets)}개 트윗 로드됨")

    # 2. 분석 및 변환
    print(f"\n[2/3] 📊 바이럴 분석 및 아이디어 변환")
    results = analyze_and_transform(tweets)

    # 결과 표시
    display_ideas(results, verbose)

    if dry_run:
        print("🏁 드라이런 완료. 영상 생성 없음.")
        return {
            "success": True,
            "ideas_count": len(results),
            "dry_run": True
        }

    # 아이디어 저장
    ideas_path = save_ideas(results, run_output_dir)

    # 3. 영상 생성 (선택)
    if auto_generate and results:
        provider_name = (provider or "veo").upper()
        print(f"\n[3/3] 🎬 자동 영상 생성 ({provider_name})")

        # 가장 점수 높은 아이디어로 영상 생성
        top_tweet, top_analysis, top_idea, top_plan = results[0]

        video_output_dir = os.path.join(run_output_dir, "video")
        video_path = generate_video(top_plan, video_output_dir, provider=provider)

        return {
            "success": True,
            "ideas_count": len(results),
            "ideas_path": ideas_path,
            "video_path": video_path,
            "top_idea": asdict(top_idea)
        }

    return {
        "success": True,
        "ideas_count": len(results),
        "ideas_path": ideas_path,
        "output_dir": run_output_dir
    }


def run_test():
    """테스트 데이터로 파이프라인 실행"""
    print("🧪 테스트 모드: 샘플 트윗으로 파이프라인 실행")
    print()

    # 샘플 트윗 데이터
    sample_tweets = [
        {
            "tweet_id": "1",
            "text": "헐 진짜 미쳤다 ㅋㅋㅋㅋㅋ AI가 그린 고양이 사진인데 실화냐",
            "author": "@ai_cat_lover",
            "retweets": 15000,
            "likes": 45000,
            "replies": 2000,
            "media": ["image.jpg"],
            "hashtags": ["#AI", "#고양이"],
            "url": "https://x.com/ai_cat_lover/status/1"
        },
        {
            "tweet_id": "2",
            "text": "이 꿀팁 아직도 모르는 사람 많던데 진짜 알려드림. 아이폰에서 이렇게 하면 배터리 2배 오래감",
            "author": "@tech_tips",
            "retweets": 8000,
            "likes": 25000,
            "replies": 500,
            "media": [],
            "hashtags": ["#아이폰", "#꿀팁"],
            "url": "https://x.com/tech_tips/status/2"
        },
        {
            "tweet_id": "3",
            "text": "오늘 출근하다가 로봇 배달원 처음 봤는데 진짜 신기하더라 ㅋㅋ 사진 찍을걸",
            "author": "@daily_worker",
            "retweets": 3000,
            "likes": 12000,
            "replies": 300,
            "media": ["video.mp4"],
            "hashtags": ["#일상", "#로봇"],
            "url": "https://x.com/daily_worker/status/3"
        },
        {
            "tweet_id": "4",
            "text": "제주도 석양 너무 예쁘다... 힐링 그 자체",
            "author": "@jeju_lover",
            "retweets": 1500,
            "likes": 8000,
            "replies": 100,
            "media": ["sunset.jpg"],
            "hashtags": ["#제주도", "#여행", "#힐링"],
            "url": "https://x.com/jeju_lover/status/4"
        },
        {
            "tweet_id": "5",
            "text": "주식 5년 해보고 깨달은 것들. 1. 존버가 답이 아님 2. 분산투자 필수 3. 뉴스 믿지마",
            "author": "@stock_guru",
            "retweets": 6000,
            "likes": 18000,
            "replies": 800,
            "media": [],
            "hashtags": ["#주식", "#투자", "#재테크"],
            "url": "https://x.com/stock_guru/status/5"
        },
    ]

    # JSON 문자열로 변환
    input_json = json.dumps(sample_tweets, ensure_ascii=False)

    result = run_pipeline(
        input_json=input_json,
        count=5,
        output_dir="/tmp/x-to-shorts-test",
        verbose=True,
        dry_run=True
    )

    print()
    print("=" * 60)
    print("✅ 테스트 완료")
    print(f"   분석된 아이디어: {result.get('ideas_count', 0)}개")
    print("=" * 60)


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="X(Twitter) 트렌드 기반 YouTube Shorts 아이디어 생성기",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 테스트 실행
  python3 generate_from_x.py --test

  # JSON 파일에서 트윗 로드
  python3 generate_from_x.py --input tweets.json --count 5

  # 영상까지 자동 생성
  python3 generate_from_x.py --input tweets.json --auto-generate

  # X 검색 쿼리 (Playwright 연동 필요)
  python3 generate_from_x.py --query "lang:ko min_retweets:1000"
"""
    )

    parser.add_argument(
        "--query", "-q",
        help="X 검색 쿼리 (예: 'lang:ko min_retweets:1000')"
    )
    parser.add_argument(
        "--input", "-i", dest="input_file",
        help="트윗 JSON 파일 경로"
    )
    parser.add_argument(
        "--count", "-c", type=int, default=5,
        help="분석할 트윗 수 (기본: 5)"
    )
    parser.add_argument(
        "--output", "-o", default="/tmp/x-to-shorts",
        help="출력 디렉토리 (기본: /tmp/x-to-shorts)"
    )
    parser.add_argument(
        "--auto-generate", "-a", action="store_true",
        help="가장 높은 점수의 아이디어로 자동 영상 생성"
    )
    parser.add_argument(
        "--dry-run", "-d", action="store_true",
        help="드라이런 (분석만, 저장 안함)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="상세 출력"
    )
    parser.add_argument(
        "--test", "-t", action="store_true",
        help="샘플 데이터로 테스트 실행"
    )
    parser.add_argument(
        "--provider", "-p",
        choices=["veo", "sora"],
        default=None,
        help="영상 생성 프로바이더: veo (기본값, $1.20~3.20/클립) 또는 sora ($0.08~0.32/클립)"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="결과를 JSON으로 출력"
    )

    args = parser.parse_args()

    if args.test:
        run_test()
        return

    if not args.query and not args.input_file:
        print("⚠️  --query 또는 --input 옵션이 필요합니다.")
        print("   테스트 실행: python3 generate_from_x.py --test")
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
        provider=args.provider
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
