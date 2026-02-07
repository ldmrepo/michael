#!/bin/bash
#
# 뉴스 수집 스크립트
# Google News RSS를 통해 키워드 기반 뉴스를 수집
#
# 사용법: fetch-news.sh <keyword> [count]
#
# 인자:
#   keyword - 검색할 키워드 (예: "AI", "비트코인", "삼성전자")
#   count   - (선택) 가져올 뉴스 개수, 기본값: 5
#
# 출력:
#   JSON 형식의 뉴스 목록
#
# 예시:
#   bash fetch-news.sh "AI" 5
#   bash fetch-news.sh "비트코인"
#

set -e

# 인자 확인
if [ $# -lt 1 ]; then
    echo "사용법: $0 <keyword> [count]"
    echo ""
    echo "예시:"
    echo "  $0 \"AI\" 5"
    echo "  $0 \"비트코인\""
    exit 1
fi

KEYWORD="$1"
COUNT="${2:-5}"

# URL 인코딩
ENCODED_KEYWORD=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$KEYWORD'))")

# Google News RSS 피드 URL (한국어)
RSS_URL="https://news.google.com/rss/search?q=${ENCODED_KEYWORD}&hl=ko&gl=KR&ceid=KR:ko"

# RSS 피드 가져오기 및 파싱
NEWS_DATA=$(curl -s "$RSS_URL" | python3 -c "
import sys
import xml.etree.ElementTree as ET
import json
import re
from html import unescape

content = sys.stdin.read()
root = ET.fromstring(content)

items = []
count = int('$COUNT')

for item in root.findall('.//item')[:count]:
    title = item.find('title')
    link = item.find('link')
    pub_date = item.find('pubDate')
    source = item.find('source')

    # 제목에서 HTML 엔티티 디코딩
    title_text = unescape(title.text) if title is not None and title.text else ''

    # 소스 추출 (제목 끝에 ' - 출처' 형식으로 포함됨)
    source_match = re.search(r' - ([^-]+)$', title_text)
    if source_match:
        source_name = source_match.group(1).strip()
        title_text = title_text[:source_match.start()].strip()
    elif source is not None and source.text:
        source_name = source.text
    else:
        source_name = 'Unknown'

    items.append({
        'title': title_text,
        'link': link.text if link is not None else '',
        'pubDate': pub_date.text if pub_date is not None else '',
        'source': source_name
    })

print(json.dumps(items, ensure_ascii=False, indent=2))
")

echo "$NEWS_DATA"
