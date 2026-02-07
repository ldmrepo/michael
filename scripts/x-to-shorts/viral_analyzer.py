#!/usr/bin/env python3
"""
X(Twitter) 바이럴 분석 엔진

트윗 데이터를 분석하여 바이럴 잠재력 점수와 콘텐츠 유형을 판정합니다.

Usage:
    python3 viral_analyzer.py --test
    python3 viral_analyzer.py --input tweets.json
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime

# =============================================================================
# Data Models
# =============================================================================

@dataclass
class TweetData:
    """트윗 데이터 구조"""
    tweet_id: str
    text: str
    author: str
    retweets: int = 0
    likes: int = 0
    replies: int = 0
    media: List[str] = None
    hashtags: List[str] = None
    collected_at: str = ""
    url: str = ""

    def __post_init__(self):
        if self.media is None:
            self.media = []
        if self.hashtags is None:
            self.hashtags = []
        if not self.collected_at:
            self.collected_at = datetime.now().isoformat()


@dataclass
class ViralAnalysis:
    """바이럴 분석 결과"""
    tweet_id: str
    viral_score: int                    # 0-100
    engagement_score: float             # 참여율 점수
    emotion: str                        # surprise, joy, anger, curiosity, neutral
    emotion_intensity: float            # 0.0-1.0
    themes: List[str]                   # 주제 태그
    meme_potential: str                 # high, medium, low
    visual_content: bool                # 미디어 포함 여부
    timeliness: str                     # trending, recent, evergreen
    recommendation: str                 # 강력 추천, 추천, 보통, 비추천
    suggested_template: str             # reaction, tutorial, story, aesthetic


# =============================================================================
# Analysis Constants
# =============================================================================

# 참여 지표 기준치
ENGAGEMENT_THRESHOLDS = {
    "viral": {"retweets": 10000, "likes": 50000, "replies": 1000},
    "hot": {"retweets": 5000, "likes": 20000, "replies": 500},
    "trending": {"retweets": 1000, "likes": 5000, "replies": 100},
    "normal": {"retweets": 100, "likes": 500, "replies": 20},
}

# 감정 키워드
EMOTION_KEYWORDS = {
    "surprise": [
        "헐", "대박", "미쳤", "충격", "실화", "ㅋㅋㅋ", "ㅎㄷㄷ", "와", "오",
        "놀라", "충격적", "믿기지", "말도안돼", "소름", "경악", "어이없",
        "wtf", "omg", "shocked", "wow", "insane", "crazy"
    ],
    "joy": [
        "행복", "기쁘", "좋아", "최고", "감사", "사랑", "귀여", "힐링",
        "웃기", "재밌", "ㅋㅋ", "ㅎㅎ", "감동", "축하", "행운",
        "happy", "love", "cute", "funny", "lol", "blessed"
    ],
    "anger": [
        "화나", "짜증", "열받", "답답", "미친", "최악", "실망", "분노",
        "억울", "불공정", "부당", "욕", "ㅅㅂ", "ㄷㅊ",
        "angry", "mad", "frustrated", "annoyed", "hate"
    ],
    "curiosity": [
        "궁금", "왜", "어떻게", "이유", "비밀", "알고", "신기", "독특",
        "처음", "발견", "연구", "팁", "꿀팁", "방법", "노하우",
        "how", "why", "secret", "tip", "hack", "discover"
    ],
}

# 밈 패턴
MEME_PATTERNS = [
    r"[ㅋ]{3,}",                    # ㅋㅋㅋㅋ
    r"[ㅎ]{3,}",                    # ㅎㅎㅎㅎ
    r"vs",                          # A vs B
    r"be like",                     # X be like
    r"me when",                     # me when
    r"pov:",                        # POV:
    r"나도 해봄",                   # 나도 해봄 류
    r"레전드",                      # 레전드
    r"썰",                          # 썰
    r"극한",                        # 극한의 X
]

# 주제 키워드
THEME_KEYWORDS = {
    "AI": ["ai", "인공지능", "챗gpt", "chatgpt", "gpt", "claude", "gemini", "딥러닝", "머신러닝"],
    "Tech": ["테크", "기술", "앱", "서비스", "스타트업", "개발", "코딩", "프로그래밍"],
    "Gaming": ["게임", "플스", "닌텐도", "스팀", "lol", "리그오브레전드", "발로란트", "오버워치"],
    "Entertainment": ["드라마", "영화", "예능", "아이돌", "kpop", "연예인", "배우"],
    "Daily": ["일상", "출근", "퇴근", "직장", "회사", "대학", "학교", "취업", "이직"],
    "Food": ["맛집", "음식", "카페", "커피", "맥주", "술", "레시피", "요리"],
    "Travel": ["여행", "휴가", "관광", "해외", "국내여행", "숙소", "항공"],
    "Finance": ["주식", "코인", "비트코인", "투자", "부동산", "금리", "환율"],
    "Health": ["건강", "운동", "다이어트", "헬스", "요가", "필라테스", "영양제"],
    "Beauty": ["뷰티", "화장품", "메이크업", "스킨케어", "패션", "옷", "코디"],
}


# =============================================================================
# Analysis Functions
# =============================================================================

def calculate_engagement_score(tweet: TweetData) -> float:
    """참여율 점수 계산 (0-100)"""
    # 가중치: RT(40%), Likes(40%), Replies(20%)
    rt_score = min(tweet.retweets / ENGAGEMENT_THRESHOLDS["viral"]["retweets"] * 100, 100)
    like_score = min(tweet.likes / ENGAGEMENT_THRESHOLDS["viral"]["likes"] * 100, 100)
    reply_score = min(tweet.replies / ENGAGEMENT_THRESHOLDS["viral"]["replies"] * 100, 100)

    return rt_score * 0.4 + like_score * 0.4 + reply_score * 0.2


def detect_emotion(text: str) -> tuple[str, float]:
    """감정 감지 및 강도 반환"""
    text_lower = text.lower()

    emotion_scores = {}
    for emotion, keywords in EMOTION_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in text_lower)
        emotion_scores[emotion] = count

    if not any(emotion_scores.values()):
        return "neutral", 0.0

    max_emotion = max(emotion_scores, key=emotion_scores.get)
    max_count = emotion_scores[max_emotion]

    # 강도: 키워드 수에 따라 0.0-1.0
    intensity = min(max_count / 5, 1.0)

    return max_emotion, intensity


def detect_themes(text: str, hashtags: List[str]) -> List[str]:
    """주제 감지"""
    text_lower = text.lower()
    combined = text_lower + " " + " ".join([h.lower() for h in hashtags])

    detected = []
    for theme, keywords in THEME_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            detected.append(theme)

    return detected if detected else ["General"]


def calculate_meme_potential(text: str) -> str:
    """밈 잠재력 평가"""
    pattern_count = sum(1 for pattern in MEME_PATTERNS if re.search(pattern, text, re.IGNORECASE))

    # 짧고 임팩트 있는 문장인지
    is_short = len(text) < 100
    has_impact = any(c * 3 in text for c in "ㅋㅎ!")

    score = pattern_count * 2 + (2 if is_short else 0) + (2 if has_impact else 0)

    if score >= 5:
        return "high"
    elif score >= 3:
        return "medium"
    return "low"


def evaluate_timeliness(text: str, hashtags: List[str]) -> str:
    """시의성 평가"""
    combined = text.lower() + " ".join([h.lower() for h in hashtags])

    # 트렌딩 신호
    trending_signals = ["속보", "긴급", "오늘", "방금", "지금", "실시간", "breaking", "just now"]

    if any(signal in combined for signal in trending_signals):
        return "trending"

    # 시간 관련 단어
    recent_signals = ["어제", "요즘", "최근", "이번주", "yesterday", "recently", "this week"]

    if any(signal in combined for signal in recent_signals):
        return "recent"

    return "evergreen"


def suggest_template(emotion: str, themes: List[str], meme_potential: str, has_media: bool) -> str:
    """최적 템플릿 추천"""
    # 감정 기반 추천
    if emotion == "surprise":
        return "reaction"

    if emotion == "curiosity":
        return "tutorial"

    # 주제 기반 추천
    aesthetic_themes = {"Travel", "Food", "Beauty"}
    if any(t in aesthetic_themes for t in themes) and has_media:
        return "aesthetic"

    story_themes = {"Daily", "Entertainment"}
    if any(t in story_themes for t in themes):
        return "story"

    # 밈 잠재력 기반
    if meme_potential == "high":
        return "reaction"

    # 기본값
    return "story"


def generate_recommendation(viral_score: int, meme_potential: str, emotion_intensity: float) -> str:
    """추천 등급 생성"""
    if viral_score >= 80 and meme_potential in ("high", "medium"):
        return "강력 추천"
    elif viral_score >= 60:
        return "추천"
    elif viral_score >= 40:
        return "보통"
    return "비추천"


# =============================================================================
# Main Analysis
# =============================================================================

def analyze_tweet(tweet: TweetData) -> ViralAnalysis:
    """트윗 바이럴 분석 수행"""
    # 개별 분석
    engagement_score = calculate_engagement_score(tweet)
    emotion, emotion_intensity = detect_emotion(tweet.text)
    themes = detect_themes(tweet.text, tweet.hashtags)
    meme_potential = calculate_meme_potential(tweet.text)
    visual_content = len(tweet.media) > 0
    timeliness = evaluate_timeliness(tweet.text, tweet.hashtags)

    # 종합 바이럴 점수 계산
    # 가중치: 참여율(30%), 감정강도(25%), 밈잠재력(20%), 시각요소(15%), 시의성(10%)
    meme_score = {"high": 100, "medium": 60, "low": 30}[meme_potential]
    visual_score = 100 if visual_content else 30
    time_score = {"trending": 100, "recent": 70, "evergreen": 50}[timeliness]

    viral_score = int(
        engagement_score * 0.30 +
        (emotion_intensity * 100) * 0.25 +
        meme_score * 0.20 +
        visual_score * 0.15 +
        time_score * 0.10
    )
    viral_score = min(viral_score, 100)

    # 템플릿 추천
    suggested_template = suggest_template(emotion, themes, meme_potential, visual_content)

    # 추천 등급
    recommendation = generate_recommendation(viral_score, meme_potential, emotion_intensity)

    return ViralAnalysis(
        tweet_id=tweet.tweet_id,
        viral_score=viral_score,
        engagement_score=engagement_score,
        emotion=emotion,
        emotion_intensity=emotion_intensity,
        themes=themes,
        meme_potential=meme_potential,
        visual_content=visual_content,
        timeliness=timeliness,
        recommendation=recommendation,
        suggested_template=suggested_template
    )


def analyze_tweets(tweets: List[TweetData]) -> List[ViralAnalysis]:
    """여러 트윗 분석 및 점수순 정렬"""
    analyses = [analyze_tweet(tweet) for tweet in tweets]
    return sorted(analyses, key=lambda x: x.viral_score, reverse=True)


# =============================================================================
# CLI Interface
# =============================================================================

def run_test():
    """테스트 실행"""
    print("=" * 60)
    print("🧪 VIRAL ANALYZER TEST")
    print("=" * 60)

    test_tweets = [
        TweetData(
            tweet_id="1",
            text="헐 진짜 미쳤다 ㅋㅋㅋㅋㅋ AI가 그린 고양이 사진인데 실화냐",
            author="@user1",
            retweets=15000,
            likes=45000,
            replies=2000,
            media=["image.jpg"],
            hashtags=["#AI", "#고양이"]
        ),
        TweetData(
            tweet_id="2",
            text="이 꿀팁 아직도 모르는 사람 많던데 진짜 알려드림. 아이폰에서 이렇게 하면...",
            author="@user2",
            retweets=8000,
            likes=25000,
            replies=500,
            media=[],
            hashtags=["#아이폰", "#꿀팁"]
        ),
        TweetData(
            tweet_id="3",
            text="오늘 출근하다가 로봇 배달원 처음 봤는데 신기하더라",
            author="@user3",
            retweets=3000,
            likes=12000,
            replies=300,
            media=["video.mp4"],
            hashtags=["#일상", "#로봇"]
        ),
        TweetData(
            tweet_id="4",
            text="제주도 석양 너무 예쁘다... 힐링",
            author="@user4",
            retweets=1500,
            likes=8000,
            replies=100,
            media=["sunset.jpg"],
            hashtags=["#제주도", "#여행", "#힐링"]
        ),
    ]

    results = analyze_tweets(test_tweets)

    for i, analysis in enumerate(results, 1):
        tweet = next(t for t in test_tweets if t.tweet_id == analysis.tweet_id)
        print(f"\n{i}. [바이럴 점수: {analysis.viral_score}] {analysis.suggested_template.upper()}")
        print(f"   원본: \"{tweet.text[:50]}...\"")
        print(f"   감정: {analysis.emotion} (강도: {analysis.emotion_intensity:.1f})")
        print(f"   주제: {', '.join(analysis.themes)}")
        print(f"   밈 잠재력: {analysis.meme_potential}")
        print(f"   추천: {analysis.recommendation}")

    print("\n" + "=" * 60)
    print("✅ Test complete")


def main():
    parser = argparse.ArgumentParser(description="X(Twitter) 바이럴 분석기")
    parser.add_argument("--test", action="store_true", help="테스트 실행")
    parser.add_argument("--input", "-i", help="입력 JSON 파일")
    parser.add_argument("--output", "-o", help="출력 JSON 파일")
    parser.add_argument("--json", action="store_true", help="JSON 형식으로 출력")

    args = parser.parse_args()

    if args.test:
        run_test()
        return

    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)

        tweets = [TweetData(**t) for t in data]
        results = analyze_tweets(tweets)

        output_data = [asdict(r) for r in results]

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            print(f"✅ Results saved to {args.output}")
        elif args.json:
            print(json.dumps(output_data, ensure_ascii=False, indent=2))
        else:
            for r in results:
                print(f"[{r.viral_score}] {r.tweet_id}: {r.recommendation} ({r.suggested_template})")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
