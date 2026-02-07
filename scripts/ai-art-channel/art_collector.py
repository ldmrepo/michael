#!/usr/bin/env python3
"""
AI 아트 전용 수집기

X(Twitter)에서 AI 아트 트윗을 수집하고 분석합니다.
기존 x-to-shorts 파이프라인과 호환됩니다.

Usage:
    python3 art_collector.py --test
    python3 art_collector.py --query "midjourney min_faves:1000" --count 5
    python3 art_collector.py --input tweets.json --dry-run
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from urllib.parse import quote

# Local imports
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent / "x-to-shorts"))

from config import (
    AI_TOOL_KEYWORDS,
    ART_STYLE_KEYWORDS,
    AI_ART_QUERIES,
    VIRAL_THRESHOLDS,
    DEFAULT_HASHTAGS,
    HOOK_TEMPLATES,
)

# Import from x-to-shorts
from viral_analyzer import TweetData, ViralAnalysis, analyze_tweet


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class AIArtData(TweetData):
    """AI 아트 확장 데이터"""
    ai_tool: str = "unknown"           # 감지된 AI 도구
    art_style: str = "unknown"         # 감지된 아트 스타일
    prompt_hint: str = ""              # 프롬프트 힌트 (있으면)
    media_urls: List[str] = field(default_factory=list)  # 이미지 URL 목록
    is_ai_art: bool = True             # AI 아트 확인 여부
    art_confidence: float = 0.0        # AI 아트 신뢰도 (0-1)

    def __post_init__(self):
        super().__post_init__()
        if not self.media_urls:
            self.media_urls = self.media.copy() if self.media else []


@dataclass
class AIArtAnalysis(ViralAnalysis):
    """AI 아트 확장 분석"""
    ai_tool: str = "unknown"
    art_style: str = "unknown"
    art_confidence: float = 0.0
    hook_suggestion: str = ""
    content_type: str = "ai_art"       # ai_art, ai_video, ai_comparison


# =============================================================================
# AI Art Detection
# =============================================================================

def detect_ai_tool(text: str, hashtags: List[str]) -> Tuple[str, float]:
    """텍스트에서 AI 도구 감지

    Returns:
        (tool_name, confidence)
    """
    combined = (text + " " + " ".join(hashtags)).lower()

    for tool, keywords in AI_TOOL_KEYWORDS.items():
        if tool == "unknown":
            continue
        for keyword in keywords:
            if keyword in combined:
                # 정확한 매칭은 높은 신뢰도
                confidence = 0.95 if keyword in text.lower() else 0.80
                return tool, confidence

    return "unknown", 0.3


def detect_art_style(text: str, hashtags: List[str]) -> Tuple[str, float]:
    """텍스트에서 아트 스타일 감지

    Returns:
        (style_name, confidence)
    """
    combined = (text + " " + " ".join(hashtags)).lower()

    matched_styles = []
    for style, keywords in ART_STYLE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in combined:
                matched_styles.append((style, 0.8))
                break

    if matched_styles:
        # 가장 구체적인 스타일 선택 (더 많은 키워드 매칭)
        return matched_styles[0]

    return "unknown", 0.3


def extract_prompt_hint(text: str) -> str:
    """텍스트에서 프롬프트 힌트 추출

    프롬프트 관련 정보가 있으면 추출 (따옴표 안, prompt: 뒤 등)
    """
    # 패턴 1: 따옴표 안의 텍스트
    quote_patterns = [
        r'"([^"]{10,100})"',
        r"'([^']{10,100})'",
        r"「([^」]{10,100})」",
    ]

    for pattern in quote_patterns:
        match = re.search(pattern, text)
        if match:
            prompt = match.group(1)
            # 프롬프트스러운 키워드가 있는지 확인
            prompt_keywords = ["style", "portrait", "landscape", "realistic", "--"]
            if any(kw in prompt.lower() for kw in prompt_keywords):
                return prompt

    # 패턴 2: prompt: 뒤의 텍스트
    prompt_pattern = r"(?:prompt|프롬프트)[:\s]+([^\n]{10,100})"
    match = re.search(prompt_pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    return ""


def calculate_art_confidence(
    tool_confidence: float,
    style_confidence: float,
    has_media: bool,
    text_indicators: int
) -> float:
    """AI 아트 신뢰도 종합 계산"""
    # 가중치: 도구(40%), 스타일(20%), 미디어(25%), 텍스트 지표(15%)
    media_score = 1.0 if has_media else 0.3
    text_score = min(text_indicators / 3, 1.0)

    confidence = (
        tool_confidence * 0.40 +
        style_confidence * 0.20 +
        media_score * 0.25 +
        text_score * 0.15
    )

    return round(confidence, 2)


def count_ai_art_indicators(text: str) -> int:
    """텍스트에서 AI 아트 관련 지표 개수"""
    indicators = [
        "ai", "인공지능", "생성", "generated", "created",
        "그려", "made", "render", "art", "아트"
    ]
    text_lower = text.lower()
    return sum(1 for ind in indicators if ind in text_lower)


# =============================================================================
# Conversion Functions
# =============================================================================

def tweet_to_ai_art_data(tweet: TweetData) -> AIArtData:
    """TweetData를 AIArtData로 변환"""
    # AI 도구 감지
    ai_tool, tool_confidence = detect_ai_tool(tweet.text, tweet.hashtags)

    # 아트 스타일 감지
    art_style, style_confidence = detect_art_style(tweet.text, tweet.hashtags)

    # 프롬프트 힌트 추출
    prompt_hint = extract_prompt_hint(tweet.text)

    # AI 아트 지표 수
    indicator_count = count_ai_art_indicators(tweet.text)

    # 종합 신뢰도
    art_confidence = calculate_art_confidence(
        tool_confidence,
        style_confidence,
        len(tweet.media) > 0,
        indicator_count
    )

    return AIArtData(
        tweet_id=tweet.tweet_id,
        text=tweet.text,
        author=tweet.author,
        retweets=tweet.retweets,
        likes=tweet.likes,
        replies=tweet.replies,
        media=tweet.media,
        hashtags=tweet.hashtags,
        collected_at=tweet.collected_at,
        url=tweet.url,
        ai_tool=ai_tool,
        art_style=art_style,
        prompt_hint=prompt_hint,
        media_urls=tweet.media.copy() if tweet.media else [],
        is_ai_art=art_confidence > 0.5,
        art_confidence=art_confidence
    )


def enhance_analysis(analysis: ViralAnalysis, art_data: AIArtData) -> AIArtAnalysis:
    """ViralAnalysis를 AIArtAnalysis로 확장"""
    # 훅 제안 생성
    hook_suggestion = generate_hook_suggestion(art_data)

    return AIArtAnalysis(
        tweet_id=analysis.tweet_id,
        viral_score=analysis.viral_score,
        engagement_score=analysis.engagement_score,
        emotion=analysis.emotion,
        emotion_intensity=analysis.emotion_intensity,
        themes=analysis.themes + ["AI Art"],  # AI Art 주제 추가
        meme_potential=analysis.meme_potential,
        visual_content=analysis.visual_content,
        timeliness=analysis.timeliness,
        recommendation=analysis.recommendation,
        suggested_template="reaction",  # AI 아트는 기본 반응형
        ai_tool=art_data.ai_tool,
        art_style=art_data.art_style,
        art_confidence=art_data.art_confidence,
        hook_suggestion=hook_suggestion,
        content_type="ai_art"
    )


def generate_hook_suggestion(art_data: AIArtData) -> str:
    """AI 아트 데이터 기반 훅 제안 생성"""
    # 스타일 기반 주제
    style_to_subject = {
        "photorealistic": "초현실적인 사진",
        "anime": "애니메이션 캐릭터",
        "fantasy": "판타지 세계",
        "cyberpunk": "사이버펑크 도시",
        "portrait": "인물화",
        "landscape": "풍경화",
        "cute": "귀여운 동물",
        "surreal": "초현실적인 이미지",
        "unknown": "놀라운 작품",
    }

    subject = style_to_subject.get(art_data.art_style, "놀라운 작품")

    # 도구 이름 정리
    tool_names = {
        "midjourney": "미드저니",
        "stable_diffusion": "스테이블 디퓨전",
        "dalle": "달리",
        "flux": "Flux",
        "unknown": "AI",
    }
    tool = tool_names.get(art_data.ai_tool, "AI")

    # 템플릿 선택 및 적용
    import random
    template = random.choice(HOOK_TEMPLATES)

    return template.format(
        subject=subject,
        tool=tool,
        prompt_hint=art_data.prompt_hint[:20] + "..." if art_data.prompt_hint else "",
        capability="이런 것까지 만들어"
    )


# =============================================================================
# Collection Functions
# =============================================================================

def collect_ai_art_from_x(query: str, count: int = 5) -> List[AIArtData]:
    """X에서 AI 아트 수집 (Playwright 연동 필요)

    실제 구현에서는 Playwright MCP를 통해 X 검색을 수행합니다.
    """
    print(f"🎨 AI 아트 검색: {query}")
    print(f"   (Playwright X 스킬 연동 필요)")
    print()

    # 검색 URL 생성 (참고용)
    search_url = f"https://x.com/search?q={quote(query)}&src=typed_query&f=live"
    print(f"   검색 URL: {search_url}")
    print()

    return []


def parse_ai_art_from_json(json_data: str) -> List[AIArtData]:
    """JSON 문자열에서 AI 아트 데이터 파싱"""
    try:
        data = json.loads(json_data)
        if isinstance(data, list):
            return [tweet_to_ai_art_data(TweetData(**t)) for t in data]
        return []
    except (json.JSONDecodeError, TypeError) as e:
        print(f"❌ JSON 파싱 오류: {e}")
        return []


def parse_ai_art_from_file(file_path: str) -> List[AIArtData]:
    """JSON 파일에서 AI 아트 데이터 로드"""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return [tweet_to_ai_art_data(TweetData(**t)) for t in data]
    return []


# =============================================================================
# Analysis Functions
# =============================================================================

def analyze_ai_art(art_data: AIArtData) -> AIArtAnalysis:
    """AI 아트 데이터 분석"""
    # 기본 바이럴 분석
    base_analysis = analyze_tweet(art_data)

    # AI 아트 확장 분석
    return enhance_analysis(base_analysis, art_data)


def analyze_ai_art_batch(art_list: List[AIArtData]) -> List[Tuple[AIArtData, AIArtAnalysis]]:
    """여러 AI 아트 분석 및 점수순 정렬"""
    results = []
    for art_data in art_list:
        analysis = analyze_ai_art(art_data)
        results.append((art_data, analysis))

    # 바이럴 점수순 정렬
    results.sort(key=lambda x: x[1].viral_score, reverse=True)
    return results


def filter_by_threshold(
    results: List[Tuple[AIArtData, AIArtAnalysis]],
    threshold: str = "recommended"
) -> List[Tuple[AIArtData, AIArtAnalysis]]:
    """바이럴 임계값으로 필터링"""
    thresholds = VIRAL_THRESHOLDS.get(threshold, VIRAL_THRESHOLDS["recommended"])
    min_score = thresholds["min_score"]
    min_likes = thresholds["min_likes"]

    return [
        (art, analysis) for art, analysis in results
        if analysis.viral_score >= min_score and art.likes >= min_likes
    ]


# =============================================================================
# Display Functions
# =============================================================================

def display_results(results: List[Tuple[AIArtData, AIArtAnalysis]], verbose: bool = False):
    """분석 결과 표시"""
    print()
    print("=" * 60)
    print("🎨 AI 아트 분석 결과")
    print("=" * 60)

    for i, (art_data, analysis) in enumerate(results, 1):
        tool_emoji = {
            "midjourney": "🎭",
            "stable_diffusion": "🎯",
            "dalle": "🎪",
            "flux": "⚡",
            "unknown": "🤖"
        }.get(art_data.ai_tool, "🤖")

        confidence_bar = "▓" * int(art_data.art_confidence * 10) + "░" * (10 - int(art_data.art_confidence * 10))

        print(f"\n{i}. [{analysis.viral_score}점] {tool_emoji} {art_data.ai_tool.upper()}")
        print(f"   원본: \"{art_data.text[:50]}{'...' if len(art_data.text) > 50 else ''}\"")
        print(f"   스타일: {art_data.art_style} | 신뢰도: [{confidence_bar}] {art_data.art_confidence:.0%}")
        print(f"   훅 제안: {analysis.hook_suggestion}")

        if verbose:
            print(f"   참여: ❤️{art_data.likes:,} 🔄{art_data.retweets:,} 💬{art_data.replies:,}")
            print(f"   미디어: {len(art_data.media_urls)}개 이미지")
            if art_data.prompt_hint:
                print(f"   프롬프트: {art_data.prompt_hint[:40]}...")
            print(f"   추천: {analysis.recommendation}")

    print()
    print("=" * 60)


def save_results(
    results: List[Tuple[AIArtData, AIArtAnalysis]],
    output_path: str
) -> str:
    """결과를 JSON 파일로 저장"""
    import os
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    output_data = []
    for art_data, analysis in results:
        output_data.append({
            "art_data": asdict(art_data),
            "analysis": asdict(analysis)
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"📄 결과 저장됨: {output_path}")
    return output_path


# =============================================================================
# CLI Interface
# =============================================================================

def run_test():
    """테스트 실행"""
    print("=" * 60)
    print("🧪 AI ART COLLECTOR TEST")
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
            "media": ["cat_ai.jpg"],
            "hashtags": ["#midjourney", "#AI아트"],
            "url": "https://x.com/ai_artist1/status/1"
        },
        {
            "tweet_id": "2",
            "text": "Stable Diffusion으로 지브리 스타일 풍경 만들어봤습니다. 프롬프트: \"ghibli style landscape, soft colors, peaceful village\"",
            "author": "@sd_creator",
            "retweets": 5000,
            "likes": 18000,
            "replies": 300,
            "media": ["ghibli_landscape.png"],
            "hashtags": ["#StableDiffusion", "#지브리", "#AI그림"],
            "url": "https://x.com/sd_creator/status/2"
        },
        {
            "tweet_id": "3",
            "text": "DALL-E 3로 사이버펑크 도시 만들어봄. 네온 조명 미쳤다",
            "author": "@dalle_fan",
            "retweets": 3500,
            "likes": 12000,
            "replies": 200,
            "media": ["cyberpunk_city.jpg"],
            "hashtags": ["#DALLE", "#사이버펑크"],
            "url": "https://x.com/dalle_fan/status/3"
        },
        {
            "tweet_id": "4",
            "text": "AI로 그린 초상화가 이 정도라니... 기술 발전 무섭다",
            "author": "@ai_observer",
            "retweets": 6000,
            "likes": 20000,
            "replies": 800,
            "media": ["portrait.jpg"],
            "hashtags": ["#AI", "#초상화"],
            "url": "https://x.com/ai_observer/status/4"
        },
        {
            "tweet_id": "5",
            "text": "귀여운 판타지 드래곤 만들어봤어요 🐉 Flux 1.1 모델 사용",
            "author": "@fantasy_art",
            "retweets": 2000,
            "likes": 8000,
            "replies": 150,
            "media": ["dragon.png", "dragon2.png"],
            "hashtags": ["#Flux", "#판타지", "#드래곤"],
            "url": "https://x.com/fantasy_art/status/5"
        },
    ]

    # 파싱 및 분석
    print(f"\n[1/3] 📥 샘플 데이터 파싱 중...")
    art_list = parse_ai_art_from_json(json.dumps(sample_tweets, ensure_ascii=False))
    print(f"   {len(art_list)}개 AI 아트 감지됨")

    print(f"\n[2/3] 📊 바이럴 분석 중...")
    results = analyze_ai_art_batch(art_list)

    print(f"\n[3/3] 📋 결과 표시")
    display_results(results, verbose=True)

    # 통계
    high_confidence = sum(1 for a, _ in results if a.art_confidence > 0.7)
    detected_tools = set(a.ai_tool for a, _ in results if a.ai_tool != "unknown")

    print("\n📊 통계:")
    print(f"   높은 신뢰도 (>70%): {high_confidence}/{len(results)}")
    print(f"   감지된 AI 도구: {', '.join(detected_tools)}")

    print("\n" + "=" * 60)
    print("✅ Test complete")


def main():
    parser = argparse.ArgumentParser(
        description="AI 아트 전용 수집기",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 테스트 실행
  python3 art_collector.py --test

  # JSON 파일에서 분석
  python3 art_collector.py --input tweets.json --verbose

  # X 검색 쿼리 (Playwright 연동 필요)
  python3 art_collector.py --query "midjourney min_faves:1000"

  # 추천 쿼리 목록 보기
  python3 art_collector.py --list-queries
"""
    )

    parser.add_argument("--test", "-t", action="store_true", help="테스트 실행")
    parser.add_argument("--input", "-i", help="입력 JSON 파일")
    parser.add_argument("--query", "-q", help="X 검색 쿼리")
    parser.add_argument("--count", "-c", type=int, default=5, help="수집할 트윗 수")
    parser.add_argument("--output", "-o", help="출력 JSON 파일")
    parser.add_argument("--verbose", "-v", action="store_true", help="상세 출력")
    parser.add_argument("--dry-run", "-d", action="store_true", help="드라이런 (분석만)")
    parser.add_argument("--threshold", choices=list(VIRAL_THRESHOLDS.keys()),
                        default="recommended", help="바이럴 임계값 (기본: recommended)")
    parser.add_argument("--list-queries", action="store_true", help="추천 쿼리 목록")
    parser.add_argument("--json", action="store_true", help="JSON 형식으로 출력")

    args = parser.parse_args()

    if args.list_queries:
        print("\n🔍 추천 AI 아트 검색 쿼리:\n")
        for i, query in enumerate(AI_ART_QUERIES, 1):
            print(f"  {i:2}. {query}")
        print()
        return

    if args.test:
        run_test()
        return

    # 데이터 수집
    art_list = []

    if args.input:
        print(f"\n📥 파일에서 로드: {args.input}")
        art_list = parse_ai_art_from_file(args.input)
    elif args.query:
        print(f"\n🔍 X 검색: {args.query}")
        art_list = collect_ai_art_from_x(args.query, args.count)

        if not art_list:
            print()
            print("⚠️  X 검색을 위해서는 Playwright MCP를 통한 브라우저 자동화가 필요합니다.")
            print()
            print("사용 방법:")
            print("  1. Claude에게 X 검색 요청")
            print("  2. 결과를 JSON으로 저장")
            print("  3. 이 스크립트에 --input 옵션으로 전달")
            print()
            print("또는 샘플 데이터로 테스트:")
            print(f"  python3 {__file__} --test")
            return
    else:
        parser.print_help()
        return

    art_list = art_list[:args.count]
    print(f"   {len(art_list)}개 AI 아트 로드됨")

    # 분석
    print(f"\n📊 분석 중...")
    results = analyze_ai_art_batch(art_list)

    # 필터링
    filtered = filter_by_threshold(results, args.threshold)
    print(f"   {args.threshold} 기준 통과: {len(filtered)}/{len(results)}")

    # 결과 표시
    if not args.json:
        display_results(filtered, verbose=args.verbose)

    # 저장
    if args.output and not args.dry_run:
        save_results(filtered, args.output)

    # JSON 출력
    if args.json:
        output_data = []
        for art_data, analysis in filtered:
            output_data.append({
                "art_data": asdict(art_data),
                "analysis": asdict(analysis)
            })
        print(json.dumps(output_data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
