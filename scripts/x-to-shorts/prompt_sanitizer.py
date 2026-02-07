#!/usr/bin/env python3
"""
Veo 3.1 프롬프트 텍스트 안전화 모듈

AI 영상 생성 시 텍스트 오류를 방지하기 위한 프롬프트 처리 도구입니다.

주요 기능:
1. "no text" 지시어 자동 추가
2. 텍스트 포함 장면 회피 가이드
3. 대사/자막 분리 처리
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


# =============================================================================
# Constants
# =============================================================================

# 텍스트 방지 지시어
NO_TEXT_DIRECTIVES = [
    "no text visible",
    "no signs",
    "no subtitles",
    "no written words",
    "no captions",
    "no logos with text",
    "clean visual without text overlays",
]

# 텍스트가 나타나기 쉬운 장면 키워드
TEXT_PRONE_SCENES = [
    "sign", "billboard", "poster", "book", "newspaper", "magazine",
    "screen", "monitor", "phone", "laptop", "computer",
    "menu", "label", "package", "brand", "logo",
    "street", "store", "shop", "restaurant",
    "간판", "책", "신문", "화면", "모니터", "메뉴", "상표",
]

# 대사 관련 패턴
DIALOGUE_PATTERNS = [
    r'"[^"]+?"',                    # "대화"
    r"'[^']+?'",                    # '대화'
    r"says?\s*[:\-]\s*.+",          # says: 대화
    r"speaking\s*[:\-]\s*.+",       # speaking: 대화
    r"말하\w*[:\-]\s*.+",            # 말한다: 대화
]

# 대체 표현
DIALOGUE_REPLACEMENTS = {
    "says": "expresses emotion naturally",
    "speaking": "communicating through gestures",
    "talking": "having a silent conversation",
    "말하": "표정으로 감정을 전달하",
    "대화": "무언의 소통",
}


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class SanitizedPrompt:
    """안전화된 프롬프트 결과"""
    original: str
    sanitized: str
    extracted_dialogue: List[str]
    warnings: List[str]
    applied_rules: List[str]


# =============================================================================
# Sanitization Functions
# =============================================================================

def add_no_text_directive(prompt: str, strength: str = "normal") -> str:
    """프롬프트에 텍스트 방지 지시어 추가

    Args:
        prompt: 원본 프롬프트
        strength: 지시어 강도 ("soft", "normal", "strict")

    Returns:
        텍스트 방지 지시어가 추가된 프롬프트
    """
    if strength == "soft":
        directive = "no text overlay"
    elif strength == "strict":
        directive = ", ".join(NO_TEXT_DIRECTIVES[:5])
    else:  # normal
        directive = "no text, no signs, no subtitles"

    # 이미 지시어가 있는지 확인
    if "no text" in prompt.lower():
        return prompt

    # 프롬프트 끝에 추가
    if prompt.rstrip().endswith("."):
        return f"{prompt.rstrip()[:-1]}, {directive}."
    else:
        return f"{prompt}, {directive}"


def detect_text_prone_elements(prompt: str) -> List[str]:
    """텍스트가 나타나기 쉬운 요소 감지"""
    prompt_lower = prompt.lower()
    detected = []

    for keyword in TEXT_PRONE_SCENES:
        if keyword.lower() in prompt_lower:
            detected.append(keyword)

    return detected


def suggest_text_safe_alternatives(elements: List[str]) -> Dict[str, str]:
    """텍스트 안전 대안 제안"""
    alternatives = {
        "sign": "building exterior without visible signage",
        "billboard": "urban landscape with blurred background",
        "screen": "device with abstract colorful display",
        "phone": "phone held showing abstract interface",
        "book": "person reading with book cover not visible",
        "newspaper": "morning scene with folded paper",
        "간판": "건물 외관 (간판 없이)",
        "화면": "추상적인 색상이 표시된 디스플레이",
    }

    suggestions = {}
    for elem in elements:
        elem_lower = elem.lower()
        if elem_lower in alternatives:
            suggestions[elem] = alternatives[elem_lower]

    return suggestions


def extract_dialogue(prompt: str) -> tuple:
    """대사 추출 및 분리

    Returns:
        (대사 제거된 프롬프트, 추출된 대사 목록)
    """
    extracted = []
    modified_prompt = prompt

    for pattern in DIALOGUE_PATTERNS:
        matches = re.findall(pattern, prompt, re.IGNORECASE)
        extracted.extend(matches)

        # 대사 제거 또는 대체
        modified_prompt = re.sub(pattern, "expressing emotion silently", modified_prompt, flags=re.IGNORECASE)

    return modified_prompt, extracted


def convert_dialogue_to_overlay(dialogue: str, timing: tuple) -> Dict[str, Any]:
    """대사를 텍스트 오버레이 설정으로 변환

    Args:
        dialogue: 대사 텍스트
        timing: (시작 시간, 종료 시간) 튜플

    Returns:
        TextOverlay 호환 딕셔너리
    """
    # 따옴표 제거
    clean_text = dialogue.strip("\"'")

    return {
        "text": clean_text,
        "start_time": timing[0],
        "end_time": timing[1],
        "style": "subtitle",
        "position": "bottom",
        "animation": "fade"
    }


def sanitize_prompt(
    prompt: str,
    no_text_strength: str = "normal",
    extract_dialogues: bool = True,
    suggest_alternatives: bool = True
) -> SanitizedPrompt:
    """프롬프트 전체 안전화 처리

    Args:
        prompt: 원본 프롬프트
        no_text_strength: 텍스트 방지 강도
        extract_dialogues: 대사 추출 여부
        suggest_alternatives: 대안 제안 여부

    Returns:
        SanitizedPrompt 객체
    """
    warnings = []
    applied_rules = []
    extracted_dialogue = []

    # 1. 텍스트 위험 요소 감지
    text_prone = detect_text_prone_elements(prompt)
    if text_prone:
        warnings.append(f"텍스트 위험 요소 감지: {', '.join(text_prone)}")
        if suggest_alternatives:
            alts = suggest_text_safe_alternatives(text_prone)
            for orig, alt in alts.items():
                warnings.append(f"  → '{orig}' 대신 '{alt}' 권장")

    # 2. 대사 추출
    modified_prompt = prompt
    if extract_dialogues:
        modified_prompt, extracted_dialogue = extract_dialogue(prompt)
        if extracted_dialogue:
            applied_rules.append("대사 추출 및 분리")
            warnings.append(f"추출된 대사 {len(extracted_dialogue)}개 → 텍스트 오버레이로 처리 권장")

    # 3. 텍스트 방지 지시어 추가
    sanitized = add_no_text_directive(modified_prompt, no_text_strength)
    applied_rules.append(f"텍스트 방지 지시어 추가 (강도: {no_text_strength})")

    return SanitizedPrompt(
        original=prompt,
        sanitized=sanitized,
        extracted_dialogue=extracted_dialogue,
        warnings=warnings,
        applied_rules=applied_rules
    )


def sanitize_shot_list(shots: List[Dict[str, Any]]) -> tuple:
    """Shot 리스트 전체 안전화

    Returns:
        (안전화된 shots, 추출된 오버레이 목록)
    """
    sanitized_shots = []
    all_overlays = []

    current_time = 0.0

    for shot in shots:
        # 프롬프트 생성 (subject 기반)
        prompt_parts = [
            shot.get("subject", ""),
            shot.get("emotion", ""),
            shot.get("optics", ""),
            shot.get("motion", ""),
            shot.get("lighting", ""),
            shot.get("style", ""),
        ]
        original_prompt = ", ".join(p for p in prompt_parts if p)

        # 안전화
        result = sanitize_prompt(original_prompt, no_text_strength="normal")

        # Shot 업데이트
        sanitized_shot = shot.copy()
        sanitized_shot["subject"] = result.sanitized.split(",")[0]  # 첫 부분만
        sanitized_shot["_sanitized"] = True
        sanitized_shot["_no_text_added"] = True

        sanitized_shots.append(sanitized_shot)

        # 대사 → 오버레이 변환
        duration = shot.get("duration", 8)
        for dialogue in result.extracted_dialogue:
            overlay = convert_dialogue_to_overlay(
                dialogue,
                (current_time + 0.5, current_time + duration - 0.5)
            )
            all_overlays.append(overlay)

        current_time += duration

    return sanitized_shots, all_overlays


# =============================================================================
# Prompt Templates
# =============================================================================

def create_text_safe_prompt(
    subject: str,
    emotion: str,
    optics: str,
    motion: str,
    lighting: str,
    style: str,
    audio: str,
    continuity: str
) -> str:
    """텍스트 안전 Veo 3.1 프롬프트 생성"""

    prompt = f"""{subject}, {emotion} mood.
{optics}, {motion}.
{lighting}, {style}.
Audio: {audio}.
{continuity}
IMPORTANT: No text, signs, subtitles, or written words visible in the scene."""

    return prompt


def create_text_safe_prompt_korean(
    subject: str,
    emotion: str,
    visual_style: str
) -> str:
    """한국어 설명 기반 텍스트 안전 프롬프트"""

    return f"""{subject}, {emotion} atmosphere, {visual_style}.
Cinematic quality, 9:16 vertical format.
No text, no Korean characters, no signs, no subtitles visible.
Clean visual composition without any written elements."""


# =============================================================================
# CLI Interface
# =============================================================================

def run_test():
    """테스트 실행"""
    print("=" * 60)
    print("🧪 PROMPT SANITIZER TEST")
    print("=" * 60)

    test_prompts = [
        'A person looking at their phone, says: "와 이거 대박이다"',
        "Street scene with coffee shop signs and billboards",
        "Close-up of book pages with visible text",
        "Dramatic sunset over the ocean, beautiful colors",
        '캐릭터가 "진짜 실화야?" 라고 말하며 놀란 표정',
    ]

    for i, prompt in enumerate(test_prompts, 1):
        print(f"\n{'='*60}")
        print(f"테스트 {i}")
        print(f"{'='*60}")
        print(f"원본: {prompt}")

        result = sanitize_prompt(prompt)

        print(f"\n안전화: {result.sanitized}")

        if result.warnings:
            print(f"\n⚠️ 경고:")
            for w in result.warnings:
                print(f"   {w}")

        if result.extracted_dialogue:
            print(f"\n💬 추출된 대사:")
            for d in result.extracted_dialogue:
                print(f"   {d}")

        print(f"\n✅ 적용된 규칙: {', '.join(result.applied_rules)}")

    print("\n" + "=" * 60)
    print("✅ Test complete")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Veo 3.1 프롬프트 텍스트 안전화")
    parser.add_argument("--test", action="store_true", help="테스트 실행")
    parser.add_argument("--prompt", "-p", help="안전화할 프롬프트")
    parser.add_argument("--strength", "-s", default="normal",
                        choices=["soft", "normal", "strict"],
                        help="텍스트 방지 강도")

    args = parser.parse_args()

    if args.test:
        run_test()
    elif args.prompt:
        result = sanitize_prompt(args.prompt, args.strength)
        print(f"원본: {result.original}")
        print(f"안전화: {result.sanitized}")
        if result.warnings:
            print(f"경고: {result.warnings}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
