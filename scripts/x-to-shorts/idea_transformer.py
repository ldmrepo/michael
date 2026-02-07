#!/usr/bin/env python3
"""
X 트윗 → YouTube Shorts 아이디어 변환기

바이럴 분석 결과를 기반으로 Shorts 아이디어 및 프로젝트 플랜을 생성합니다.
텍스트 안전 프롬프트 생성 및 텍스트 오버레이 설정을 포함합니다.

Usage:
    python3 idea_transformer.py --test
    python3 idea_transformer.py --tweet "트윗 내용" --template reaction
"""

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any
from pathlib import Path

# Import local modules from same directory
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from viral_analyzer import TweetData, ViralAnalysis, analyze_tweet
from prompt_sanitizer import sanitize_prompt, create_text_safe_prompt
from text_overlay import TextOverlay, generate_shorts_overlays


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class ShortsIdea:
    """Shorts 아이디어"""
    source_tweet: str               # 원본 트윗 URL/ID
    source_text: str                # 원본 트윗 내용
    brief: str                      # 아이디어 요약 (agentic_video용)
    viral_score: int                # 바이럴 점수
    template_type: str              # reaction, tutorial, story, aesthetic
    hook: str                       # 첫 3초 훅
    structure: str                  # 영상 구조 설명
    key_visual: str                 # 핵심 비주얼 아이디어
    audio_suggestion: str           # 오디오 제안
    hashtags: List[str]             # 추천 해시태그
    estimated_duration: int = 60    # 추정 영상 길이 (초)
    text_overlays: List[Dict] = field(default_factory=list)  # FFmpeg 텍스트 오버레이 설정


@dataclass
class ProjectPlan:
    """agentic_video.py 호환 프로젝트 플랜"""
    source_tweet: str
    brief: str
    viral_score: int
    template_type: str
    continuity: Dict[str, Any]
    beat_sheet: Dict[str, Any]
    shots: List[Dict[str, Any]]
    text_overlays: List[Dict[str, Any]] = field(default_factory=list)  # 텍스트 오버레이 설정
    text_safe_prompts: bool = True  # 텍스트 안전 프롬프트 사용 여부


# =============================================================================
# Template Definitions
# =============================================================================

TRANSFORM_TEMPLATES = {
    "reaction": {
        "name": "반응형",
        "description": "충격적 사실 공개, 리액션 중심",
        "hook_format": "헐, {핵심} 실화냐?",
        "structure": "문제제시 → 반응 → 해설",
        "beat_sheet": {
            "hook": "충격적인 시각 자료와 함께 '이거 실화?' 느낌의 오프닝",
            "setup": "원본 콘텐츠/현상 보여주기",
            "development": "리액션과 추가 정보, 왜 이게 화제인지",
            "climax": "가장 놀라운 포인트 강조",
            "resolution": "마무리 코멘트 + 구독 유도"
        },
        "continuity": {
            "color_palette": "high contrast, vibrant colors",
            "lighting_setup": "dramatic rim lighting",
            "camera_style": "dynamic zooms and push-ins",
            "audio_theme": "tension building with surprise reveal"
        },
        "shot_style": {
            "optics": "close-up with quick cuts",
            "motion": "fast zooms, whip pans",
            "lighting": "dramatic contrast",
            "style": "high energy, meme-like"
        }
    },

    "tutorial": {
        "name": "정보형",
        "description": "꿀팁, 노하우 전달",
        "hook_format": "이거 모르면 손해! {주제}",
        "structure": "문제 → 해결책 → 결과",
        "beat_sheet": {
            "hook": "'이거 알면 인생 바뀝니다' 스타일 오프닝",
            "setup": "문제 상황 또는 기존 방법의 불편함 제시",
            "development": "단계별 해결책 시연",
            "climax": "결과물 또는 효과 보여주기",
            "resolution": "마무리 팁 + 더 많은 팁 예고"
        },
        "continuity": {
            "color_palette": "clean, bright tones",
            "lighting_setup": "soft even lighting",
            "camera_style": "steady shots with clear focus",
            "audio_theme": "upbeat background with clear narration"
        },
        "shot_style": {
            "optics": "medium shots, detail close-ups",
            "motion": "smooth dolly, slow reveals",
            "lighting": "bright and clear",
            "style": "clean, professional"
        }
    },

    "story": {
        "name": "스토리형",
        "description": "일상 에피소드, 스토리텔링",
        "hook_format": "어제 {상황}했는데...",
        "structure": "상황 → 전개 → 반전",
        "beat_sheet": {
            "hook": "호기심 유발하는 일상 순간으로 시작",
            "setup": "배경 상황 설명, 캐릭터/장소 소개",
            "development": "이야기 전개, 점점 고조되는 텐션",
            "climax": "예상치 못한 반전 또는 하이라이트",
            "resolution": "에필로그, 교훈 또는 웃긴 마무리"
        },
        "continuity": {
            "color_palette": "warm, relatable tones",
            "lighting_setup": "natural ambient lighting",
            "camera_style": "vlog-style, handheld feel",
            "audio_theme": "storytelling narration with mood music"
        },
        "shot_style": {
            "optics": "varied angles, POV shots",
            "motion": "organic camera movements",
            "lighting": "natural, situational",
            "style": "authentic, relatable"
        }
    },

    "aesthetic": {
        "name": "감성형",
        "description": "비주얼 중심, 힐링/감성",
        "hook_format": "{장면}의 순간",
        "structure": "장면1 → 장면2 → 마무리",
        "beat_sheet": {
            "hook": "시각적으로 아름다운 장면으로 시선 사로잡기",
            "setup": "분위기 있는 장면 전개",
            "development": "시각적 여정, 변화하는 풍경/순간",
            "climax": "가장 인상적인 비주얼 클라이맥스",
            "resolution": "여운 있는 마무리, 루프 가능한 엔딩"
        },
        "continuity": {
            "color_palette": "cinematic color grading",
            "lighting_setup": "golden hour, atmospheric",
            "camera_style": "smooth cinematic movements",
            "audio_theme": "ambient music, ASMR elements"
        },
        "shot_style": {
            "optics": "wide establishing, beauty shots",
            "motion": "slow graceful camera moves",
            "lighting": "golden hour, soft diffused",
            "style": "cinematic, dreamy"
        }
    }
}


# =============================================================================
# Transformation Functions
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
            timeout=60
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def generate_brief(tweet: TweetData, analysis: ViralAnalysis, template: dict) -> str:
    """트윗에서 영상 브리프 생성"""
    prompt = f"""다음 트윗을 기반으로 YouTube Shorts 영상 아이디어를 한 문장으로 요약해주세요.

트윗: "{tweet.text}"
감정: {analysis.emotion}
주제: {', '.join(analysis.themes)}
템플릿 유형: {template['name']} - {template['description']}

한국어로 60자 이내, 영상 내용만 (예: "AI가 그린 고양이 사진 vs 실제 고양이 비교 리액션"):"""

    result = call_claude(prompt, "YouTube Shorts 크리에이터")

    if result:
        return result.strip().strip('"').strip("'")

    # Fallback
    return f"{analysis.themes[0] if analysis.themes else '일상'} 관련 {template['name']} 콘텐츠"


def generate_hook(tweet: TweetData, analysis: ViralAnalysis, template: dict) -> str:
    """첫 3초 훅 생성"""
    hook_format = template["hook_format"]

    prompt = f"""다음 트윗을 기반으로 YouTube Shorts 첫 3초 훅을 만들어주세요.

트윗: "{tweet.text}"
템플릿: {hook_format}

15자 이내, 시청자 멈추게 할 강렬한 한 문장:"""

    result = call_claude(prompt, "YouTube Shorts 크리에이터, 훅 전문가")

    if result:
        return result.strip().strip('"').strip("'")

    # Fallback based on emotion
    if analysis.emotion == "surprise":
        return "이거 실화야?"
    elif analysis.emotion == "curiosity":
        return "이거 몰랐죠?"
    elif analysis.emotion == "joy":
        return "이거 보면 기분 좋아져요"
    return "이거 한번 보세요"


def generate_key_visual(tweet: TweetData, analysis: ViralAnalysis, template: dict) -> str:
    """핵심 비주얼 아이디어 생성"""
    prompt = f"""다음 트윗을 YouTube Shorts 영상으로 만들 때 핵심 비주얼을 설명해주세요.

트윗: "{tweet.text}"
스타일: {template['shot_style']['style']}
분위기: {template['continuity']['color_palette']}

30자 이내로 핵심 장면만:"""

    result = call_claude(prompt, "영상 디렉터")

    if result:
        return result.strip()

    # Fallback
    return f"{analysis.themes[0] if analysis.themes else '주제'} 관련 {template['shot_style']['style']} 비주얼"


def generate_audio_suggestion(analysis: ViralAnalysis, template: dict) -> str:
    """오디오 제안 생성"""
    base_theme = template["continuity"]["audio_theme"]

    if analysis.emotion == "surprise":
        return f"{base_theme}, dramatic reveal sound effects"
    elif analysis.emotion == "joy":
        return f"{base_theme}, upbeat trending sound"
    elif analysis.emotion == "curiosity":
        return f"{base_theme}, mystery/discovery vibes"
    return base_theme


def generate_hashtags(analysis: ViralAnalysis, tweet: TweetData) -> List[str]:
    """추천 해시태그 생성"""
    hashtags = ["#shorts", "#유튜브쇼츠"]

    # 주제 기반
    theme_tags = {
        "AI": "#AI #인공지능",
        "Tech": "#테크 #기술",
        "Daily": "#일상 #브이로그",
        "Food": "#맛집 #푸드",
        "Travel": "#여행 #travel",
        "Gaming": "#게임 #gaming",
        "Entertainment": "#연예 #kpop",
        "Finance": "#투자 #재테크",
        "Health": "#건강 #운동",
        "Beauty": "#뷰티 #makeup",
    }

    for theme in analysis.themes:
        if theme in theme_tags:
            hashtags.extend(theme_tags[theme].split())

    # 원본 트윗 해시태그 일부 포함
    if tweet.hashtags:
        hashtags.extend([h for h in tweet.hashtags[:2] if h not in hashtags])

    return hashtags[:7]  # 최대 7개


def generate_text_overlays_for_idea(idea_hook: str, hashtags: List[str], duration: int = 60) -> List[Dict]:
    """아이디어 기반 텍스트 오버레이 생성"""
    overlays = generate_shorts_overlays(
        hook_text=idea_hook,
        hashtags=hashtags,
        duration=float(duration)
    )
    # TextOverlay 객체를 딕셔너리로 변환
    return [asdict(o) for o in overlays]


def transform_to_idea(tweet: TweetData, analysis: ViralAnalysis) -> ShortsIdea:
    """트윗+분석 결과를 Shorts 아이디어로 변환"""
    template_type = analysis.suggested_template
    template = TRANSFORM_TEMPLATES[template_type]

    # 각 요소 생성
    brief = generate_brief(tweet, analysis, template)
    hook = generate_hook(tweet, analysis, template)
    key_visual = generate_key_visual(tweet, analysis, template)
    audio_suggestion = generate_audio_suggestion(analysis, template)
    hashtags = generate_hashtags(analysis, tweet)

    # 텍스트 오버레이 생성
    text_overlays = generate_text_overlays_for_idea(hook, hashtags, 60)

    return ShortsIdea(
        source_tweet=tweet.url or tweet.tweet_id,
        source_text=tweet.text,
        brief=brief,
        viral_score=analysis.viral_score,
        template_type=template_type,
        hook=hook,
        structure=template["structure"],
        key_visual=key_visual,
        audio_suggestion=audio_suggestion,
        hashtags=hashtags,
        text_overlays=text_overlays
    )


def make_text_safe_subject(subject: str) -> str:
    """Subject를 텍스트 안전 버전으로 변환"""
    result = sanitize_prompt(subject, no_text_strength="normal")
    return result.sanitized


def transform_to_project_plan(idea: ShortsIdea, text_safe: bool = True) -> ProjectPlan:
    """ShortsIdea를 agentic_video.py 호환 ProjectPlan으로 변환

    Args:
        idea: ShortsIdea 객체
        text_safe: True면 텍스트 안전 프롬프트 생성 (기본값)
    """
    template = TRANSFORM_TEMPLATES[idea.template_type]

    # Beat sheet
    beat_sheet = template["beat_sheet"].copy()
    beat_sheet["hook"] = f"{idea.hook} - {beat_sheet['hook']}"

    # Continuity
    continuity = template["continuity"].copy()

    # Shots (기본 7개 샷) - 텍스트 안전 프롬프트 적용
    shot_style = template["shot_style"]

    # 텍스트 안전 버전의 subject 생성
    def safe_subject(text: str) -> str:
        if text_safe:
            return make_text_safe_subject(text)
        return text

    shots = [
        {
            "id": 1,
            "subject": safe_subject(f"Visual representation of {idea.brief}, dramatic opening"),
            "emotion": "attention-grabbing",
            "optics": "extreme close-up",
            "motion": "quick zoom in",
            "lighting": "dramatic",
            "style": shot_style["style"],
            "audio": "hook sound (text overlay will be added in post)",
            "continuity": "opening hook",
            "duration": 4,
            "_text_safe": True
        },
        {
            "id": 2,
            "subject": safe_subject(beat_sheet["setup"]),
            "emotion": "establishing",
            "optics": shot_style["optics"],
            "motion": shot_style["motion"],
            "lighting": shot_style["lighting"],
            "style": shot_style["style"],
            "audio": idea.audio_suggestion,
            "continuity": "setup scene",
            "duration": 8,
            "_text_safe": True
        },
        {
            "id": 3,
            "subject": safe_subject(beat_sheet["development"]),
            "emotion": "engaging",
            "optics": shot_style["optics"],
            "motion": shot_style["motion"],
            "lighting": shot_style["lighting"],
            "style": shot_style["style"],
            "audio": idea.audio_suggestion,
            "continuity": "main content",
            "duration": 8,
            "_text_safe": True
        },
        {
            "id": 4,
            "subject": safe_subject(idea.key_visual),
            "emotion": "focused",
            "optics": "detail close-up",
            "motion": "slow dolly",
            "lighting": shot_style["lighting"],
            "style": shot_style["style"],
            "audio": idea.audio_suggestion,
            "continuity": "key visual",
            "duration": 8,
            "_text_safe": True
        },
        {
            "id": 5,
            "subject": safe_subject(beat_sheet["development"]),
            "emotion": "building",
            "optics": shot_style["optics"],
            "motion": shot_style["motion"],
            "lighting": shot_style["lighting"],
            "style": shot_style["style"],
            "audio": "music builds",
            "continuity": "continued development",
            "duration": 8,
            "_text_safe": True
        },
        {
            "id": 6,
            "subject": safe_subject(beat_sheet["climax"]),
            "emotion": "peak moment",
            "optics": "dynamic angle",
            "motion": "dramatic movement",
            "lighting": "dramatic contrast",
            "style": shot_style["style"],
            "audio": "climax audio",
            "continuity": "climax",
            "duration": 8,
            "_text_safe": True
        },
        {
            "id": 7,
            "subject": safe_subject(beat_sheet["resolution"]),
            "emotion": "satisfying",
            "optics": "wide shot",
            "motion": "gentle pull back",
            "lighting": "warm",
            "style": shot_style["style"],
            "audio": "resolution (text overlay for CTA)",
            "continuity": "ending",
            "duration": 8,
            "_text_safe": True
        },
    ]

    return ProjectPlan(
        source_tweet=idea.source_tweet,
        brief=idea.brief,
        viral_score=idea.viral_score,
        template_type=idea.template_type,
        continuity=continuity,
        beat_sheet=beat_sheet,
        shots=shots,
        text_overlays=idea.text_overlays,
        text_safe_prompts=text_safe
    )


# =============================================================================
# CLI Interface
# =============================================================================

def run_test():
    """테스트 실행"""
    print("=" * 60)
    print("🎬 IDEA TRANSFORMER TEST")
    print("=" * 60)

    test_tweet = TweetData(
        tweet_id="test123",
        text="헐 진짜 미쳤다 ㅋㅋㅋㅋㅋ AI가 그린 고양이 사진인데 실화냐",
        author="@user1",
        retweets=15000,
        likes=45000,
        replies=2000,
        media=["image.jpg"],
        hashtags=["#AI", "#고양이"],
        url="https://x.com/user1/status/test123"
    )

    # 분석
    analysis = analyze_tweet(test_tweet)
    print(f"\n📊 분석 결과:")
    print(f"   바이럴 점수: {analysis.viral_score}")
    print(f"   감정: {analysis.emotion}")
    print(f"   추천 템플릿: {analysis.suggested_template}")

    # 아이디어 생성
    print(f"\n🎨 아이디어 생성 중...")
    idea = transform_to_idea(test_tweet, analysis)

    print(f"\n💡 Shorts 아이디어:")
    print(f"   브리프: {idea.brief}")
    print(f"   훅: {idea.hook}")
    print(f"   구조: {idea.structure}")
    print(f"   핵심 비주얼: {idea.key_visual}")
    print(f"   오디오: {idea.audio_suggestion}")
    print(f"   해시태그: {' '.join(idea.hashtags)}")

    # 텍스트 오버레이 확인
    print(f"\n🔤 텍스트 오버레이: {len(idea.text_overlays)}개")
    for overlay in idea.text_overlays:
        print(f"   [{overlay.get('style', 'unknown')}] {overlay.get('start_time', 0):.1f}s ~ {overlay.get('end_time', 0):.1f}s: {overlay.get('text', '')[:30]}...")

    # 프로젝트 플랜 생성
    print(f"\n📋 프로젝트 플랜 생성 중 (텍스트 안전 모드)...")
    plan = transform_to_project_plan(idea, text_safe=True)

    print(f"\n📝 프로젝트 플랜:")
    print(f"   Beat Sheet Hook: {plan.beat_sheet['hook'][:50]}...")
    print(f"   Shot 수: {len(plan.shots)}")
    print(f"   총 길이: {sum(s['duration'] for s in plan.shots)}초")
    print(f"   텍스트 안전 프롬프트: {'✅' if plan.text_safe_prompts else '❌'}")
    print(f"   텍스트 오버레이: {len(plan.text_overlays)}개")

    # 첫 번째 샷의 subject 확인
    if plan.shots:
        print(f"\n   샷 1 Subject (안전화됨):")
        print(f"   {plan.shots[0]['subject'][:80]}...")

    print("\n" + "=" * 60)
    print("✅ Test complete")


def main():
    parser = argparse.ArgumentParser(description="X 트윗 → Shorts 아이디어 변환기")
    parser.add_argument("--test", action="store_true", help="테스트 실행")
    parser.add_argument("--tweet", "-t", help="트윗 내용")
    parser.add_argument("--template", choices=list(TRANSFORM_TEMPLATES.keys()),
                        help="강제 템플릿 지정")
    parser.add_argument("--json", action="store_true", help="JSON 형식 출력")

    args = parser.parse_args()

    if args.test:
        run_test()
        return

    if args.tweet:
        # 간단한 테스트용 트윗 생성
        tweet = TweetData(
            tweet_id="manual",
            text=args.tweet,
            author="@manual",
            retweets=1000,
            likes=5000,
            replies=100
        )

        analysis = analyze_tweet(tweet)

        if args.template:
            analysis.suggested_template = args.template

        idea = transform_to_idea(tweet, analysis)
        plan = transform_to_project_plan(idea)

        if args.json:
            output = {
                "idea": asdict(idea),
                "plan": {
                    "source_tweet": plan.source_tweet,
                    "brief": plan.brief,
                    "viral_score": plan.viral_score,
                    "template_type": plan.template_type,
                    "continuity": plan.continuity,
                    "beat_sheet": plan.beat_sheet,
                    "shots": plan.shots,
                    "text_overlays": plan.text_overlays,
                    "text_safe_prompts": plan.text_safe_prompts
                }
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            print(f"\n💡 {idea.brief}")
            print(f"   훅: {idea.hook}")
            print(f"   템플릿: {idea.template_type}")
            print(f"   구조: {idea.structure}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
