#!/bin/bash
#
# 명상 TTS 생성 스크립트
# OpenAI TTS API를 사용하여 텍스트를 음성으로 변환
#
# 사용법: tts-generate.sh <text_file> <output_file> [voice]
#
# 인자:
#   text_file   - 명상 스크립트가 담긴 텍스트 파일 경로
#   output_file - 출력 MP3 파일 경로
#   voice       - (선택) 음성 종류: alloy, echo, fable, onyx, nova, shimmer
#                 기본값: nova (차분한 여성 목소리, 명상에 적합)
#
# 환경 변수:
#   OPENAI_API_KEY - OpenAI API 키 (필수)
#
# 예시:
#   bash tts-generate.sh /tmp/meditation/script.txt /tmp/meditation/output.mp3
#   bash tts-generate.sh /tmp/meditation/script.txt /tmp/meditation/output.mp3 shimmer
#

set -e

# 인자 확인
if [ $# -lt 2 ]; then
    echo "사용법: $0 <text_file> <output_file> [voice]"
    echo ""
    echo "음성 옵션:"
    echo "  nova    - 차분한 여성 (기본값, 명상 추천)"
    echo "  shimmer - 부드러운 여성"
    echo "  onyx    - 깊은 남성"
    echo "  alloy   - 중성적"
    echo "  echo    - 남성"
    echo "  fable   - 여성 (밝은)"
    exit 1
fi

TEXT_FILE="$1"
OUTPUT="$2"
VOICE="${3:-nova}"

# 환경 변수 확인
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ OPENAI_API_KEY 환경 변수가 설정되지 않았습니다."
    exit 1
fi

# 입력 파일 확인
if [ ! -f "$TEXT_FILE" ]; then
    echo "❌ 텍스트 파일을 찾을 수 없습니다: $TEXT_FILE"
    exit 1
fi

# 텍스트 읽기
TEXT=$(cat "$TEXT_FILE")

# 텍스트 길이 확인 (OpenAI TTS 최대 4096자)
TEXT_LENGTH=${#TEXT}
if [ "$TEXT_LENGTH" -gt 4096 ]; then
    echo "⚠️ 텍스트가 너무 깁니다 ($TEXT_LENGTH자). 4096자로 자릅니다."
    TEXT="${TEXT:0:4096}"
fi

# 출력 디렉토리 생성
OUTPUT_DIR=$(dirname "$OUTPUT")
mkdir -p "$OUTPUT_DIR"

echo "🎙️ TTS 변환 중..."
echo "  텍스트: ${TEXT_LENGTH}자"
echo "  음성: $VOICE"
echo "  출력: $OUTPUT"

# JSON 페이로드 생성 (특수 문자 이스케이프)
JSON_PAYLOAD=$(jq -n \
    --arg model "tts-1" \
    --arg input "$TEXT" \
    --arg voice "$VOICE" \
    '{
        model: $model,
        input: $input,
        voice: $voice,
        speed: 0.9
    }')

# OpenAI TTS API 호출
HTTP_CODE=$(curl -s -w "%{http_code}" -o "$OUTPUT" \
    https://api.openai.com/v1/audio/speech \
    -H "Authorization: Bearer $OPENAI_API_KEY" \
    -H "Content-Type: application/json" \
    -d "$JSON_PAYLOAD")

# 응답 확인
if [ "$HTTP_CODE" != "200" ]; then
    echo "❌ TTS API 오류 (HTTP $HTTP_CODE)"
    if [ -f "$OUTPUT" ]; then
        cat "$OUTPUT"
        rm "$OUTPUT"
    fi
    exit 1
fi

# 파일 크기 확인
FILE_SIZE=$(stat -f%z "$OUTPUT" 2>/dev/null || stat -c%s "$OUTPUT" 2>/dev/null)
echo "✅ 생성 완료: $OUTPUT ($FILE_SIZE bytes)"
