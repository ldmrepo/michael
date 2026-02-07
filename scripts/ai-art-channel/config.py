#!/usr/bin/env python3
"""
AI 아트 채널 설정

채널 컨셉 및 파이프라인 설정값
"""

# =============================================================================
# Channel Configuration
# =============================================================================

CHANNEL_NAME = "실화냐 AI"
CHANNEL_DESCRIPTION = "AI가 만든 놀라운 작품들, 실화냐?"

# 콘텐츠 포맷 (60초 기준)
VIDEO_FORMAT = {
    "duration_seconds": 60,
    "hook_duration": 3,        # 0-3초: 훅
    "reveal_duration": 12,     # 3-15초: 원본 공개
    "reaction_duration": 20,   # 15-35초: 리액션/설명
    "compare_duration": 15,    # 35-50초: 비교/추가
    "cta_duration": 10,        # 50-60초: CTA
    "aspect_ratio": "9:16",
    "resolution": "1080x1920",
}

# 기본 해시태그
DEFAULT_HASHTAGS = [
    "#shorts",
    "#AIart",
    "#AI그림",
    "#미드저니",
    "#인공지능",
    "#실화냐AI",
]

# =============================================================================
# AI Art Detection
# =============================================================================

# AI 도구 키워드
AI_TOOL_KEYWORDS = {
    "midjourney": [
        "midjourney", "미드저니", "mj", "mid journey", "--v5", "--v6", "--ar"
    ],
    "stable_diffusion": [
        "stable diffusion", "sd", "스테이블", "stablediffusion", "sdxl", "sd3"
    ],
    "dalle": [
        "dall-e", "dalle", "달리", "dall·e", "openai art"
    ],
    "flux": [
        "flux", "플럭스", "flux.1", "black forest labs"
    ],
    "firefly": [
        "firefly", "파이어플라이", "adobe firefly"
    ],
    "leonardo": [
        "leonardo", "레오나르도", "leonardo.ai"
    ],
    "sora": [
        "sora", "소라", "openai sora"
    ],
    "runway": [
        "runway", "런웨이", "gen-2", "gen2"
    ],
    "pika": [
        "pika", "피카", "pika labs"
    ],
    "kling": [
        "kling", "클링", "kuaishou"
    ],
    "unknown": []  # 감지 실패 시
}

# 아트 스타일 키워드
ART_STYLE_KEYWORDS = {
    "photorealistic": [
        "realistic", "photorealistic", "hyper realistic", "사실적", "포토리얼",
        "real", "lifelike", "photography style"
    ],
    "anime": [
        "anime", "애니메이션", "애니", "manga", "일본풍", "japanese style",
        "ghibli", "지브리", "cel shaded"
    ],
    "fantasy": [
        "fantasy", "판타지", "magical", "dragon", "elf", "dwarf",
        "mythical", "enchanted", "fairy"
    ],
    "cyberpunk": [
        "cyberpunk", "사이버펑크", "neon", "futuristic", "sci-fi",
        "dystopian", "tech", "holographic"
    ],
    "oil_painting": [
        "oil painting", "유화", "classical", "renaissance",
        "impressionist", "baroque", "fine art"
    ],
    "watercolor": [
        "watercolor", "수채화", "aquarelle", "soft colors",
        "pastel", "delicate"
    ],
    "portrait": [
        "portrait", "초상화", "face", "headshot", "character",
        "person", "model"
    ],
    "landscape": [
        "landscape", "풍경", "scenery", "nature", "mountains",
        "ocean", "forest", "city"
    ],
    "surreal": [
        "surreal", "초현실적", "dreamlike", "abstract",
        "impossible", "distorted", "weird"
    ],
    "cute": [
        "cute", "귀여운", "kawaii", "adorable", "chibi",
        "pet", "animal"
    ],
}

# =============================================================================
# X (Twitter) Search Queries
# =============================================================================

# AI 아트 전용 검색 쿼리
AI_ART_QUERIES = [
    # 고참여도 미드저니
    "midjourney min_faves:1000 filter:images",
    "미드저니 min_faves:500 filter:images lang:ko",

    # Stable Diffusion
    "stable diffusion min_faves:500 filter:images",
    "스테이블 디퓨전 min_faves:300 filter:images lang:ko",

    # DALL-E
    "dall-e min_faves:500 filter:images",
    "달리 AI min_faves:300 filter:images lang:ko",

    # 일반 AI 아트
    "AI art min_retweets:500 filter:images",
    "AI 그림 min_faves:300 filter:images lang:ko",
    "AI가 그린 min_faves:200 filter:images lang:ko",
    "AI로 만든 min_faves:200 filter:images lang:ko",

    # 감정 기반 (바이럴 잠재력 높음)
    "(실화 OR 대박 OR 미쳤) AI filter:images lang:ko",
    "(wow OR insane OR crazy) AI art filter:images",

    # 특정 주제 (트렌딩)
    "AI 고양이 filter:images min_faves:200 lang:ko",
    "AI portrait min_faves:500 filter:images",
    "AI landscape min_faves:500 filter:images",
]

# =============================================================================
# Viral Thresholds (AI Art Specific)
# =============================================================================

# AI 아트 콘텐츠는 시각적이므로 기준이 약간 다름
VIRAL_THRESHOLDS = {
    "must_publish": {  # 무조건 발행
        "min_score": 90,
        "min_likes": 10000,
    },
    "high_priority": {  # 고우선순위
        "min_score": 80,
        "min_likes": 5000,
    },
    "recommended": {  # 추천
        "min_score": 70,
        "min_likes": 2000,
    },
    "consider": {  # 고려
        "min_score": 60,
        "min_likes": 1000,
    },
}

# =============================================================================
# Video Generation Modes
# =============================================================================

# 비용 최적화 모드
VIDEO_MODES = {
    "image_only": {
        "description": "이미지 기반 Ken Burns 효과 (비용 $0)",
        "cost_per_video": 0.0,
        "quality": "good",
        "use_veo": False,
        "min_score": 0,  # 모든 점수에 사용 가능
    },
    "hybrid": {
        "description": "하이브리드 (이미지 + 부분 Veo)",
        "cost_per_video": 1.5,
        "quality": "great",
        "use_veo": True,
        "min_score": 85,  # 85점 이상만
    },
    "full_veo": {
        "description": "풀 Veo 3.1 영상 생성",
        "cost_per_video": 3.0,
        "quality": "premium",
        "use_veo": True,
        "min_score": 95,  # 95점 이상만
    },
}

# =============================================================================
# Content Templates
# =============================================================================

# AI 아트 전용 훅 템플릿
HOOK_TEMPLATES = [
    "AI가 그린 {subject}인데... 실화냐?",
    "{subject} 이거 진짜 AI가 만든 거야?",
    "AI로 만든 {subject}, 사람이 그린 줄...",
    "{tool}로 {subject} 만들었는데 충격",
    "이게 AI라고? {subject} 퀄리티 실화",
    "AI가 {subject} 그리면 생기는 일",
]

# 리액션 텍스트 템플릿
REACTION_TEMPLATES = [
    "이건 {tool}로 만든 건데요",
    "프롬프트는 '{prompt_hint}'",
    "실제로 이 정도면 상업용 가능",
    "AI 아트 퀄리티가 미쳤네",
    "이제 AI가 {capability}",
]

# CTA 템플릿
CTA_TEMPLATES = [
    "더 많은 AI 아트 보러 오세요!",
    "구독하면 AI 아트 최신 트렌드 알림!",
    "좋아요 누르면 더 많이 올릴게요",
    "이런 AI 아트 더 보고 싶으면 구독!",
]

# =============================================================================
# Ken Burns Effect Settings
# =============================================================================

KEN_BURNS_PRESETS = {
    "zoom_in_slow": {
        "description": "천천히 줌인 (드라마틱 공개)",
        "scale_start": 1.0,
        "scale_end": 1.3,
        "duration": 5.0,
    },
    "zoom_out_slow": {
        "description": "천천히 줌아웃 (전체 공개)",
        "scale_start": 1.3,
        "scale_end": 1.0,
        "duration": 5.0,
    },
    "pan_left_to_right": {
        "description": "왼쪽에서 오른쪽 패닝",
        "x_start": 0,
        "x_end": "w-iw",
        "duration": 6.0,
    },
    "pan_right_to_left": {
        "description": "오른쪽에서 왼쪽 패닝",
        "x_start": "w-iw",
        "x_end": 0,
        "duration": 6.0,
    },
    "diagonal_zoom": {
        "description": "대각선 줌 (역동적)",
        "scale_start": 1.0,
        "scale_end": 1.2,
        "x_offset_start": 0,
        "x_offset_end": 100,
        "y_offset_start": 0,
        "y_offset_end": 100,
        "duration": 4.0,
    },
}

# =============================================================================
# File Paths
# =============================================================================

import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

# 출력 디렉토리
OUTPUT_DIR = os.environ.get("AI_ART_OUTPUT_DIR", "/tmp/ai-art-channel")
CACHE_DIR = os.path.join(OUTPUT_DIR, "cache")
THUMBNAILS_DIR = os.path.join(OUTPUT_DIR, "thumbnails")

# x-to-shorts 모듈 경로
X_TO_SHORTS_DIR = SCRIPT_DIR.parent / "x-to-shorts"
YOUTUBE_SHORTS_DIR = SCRIPT_DIR.parent / "youtube-shorts"
