---
name: finance
description: |
  금융 정보 조회 및 분석 스킬. 주식, 암호화폐 시세 조회, 환율 변환.
  다음 질문에 사용: "주가", "비트코인", "이더리움", "환율", "시세", "코인", "달러", "원화"
allowed-tools: Bash(bash:*), Read
---

# Finance Skill

금융 데이터 조회 및 분석을 위한 스킬입니다.

## 사용 가능한 API 스크립트

프로젝트 루트 기준 `scripts/finance/` 디렉토리에 다음 스크립트가 있습니다:

| 스크립트 | 용도 | 사용법 |
|---------|------|--------|
| `fetch-stock.sh` | 단일 주식 시세 | `fetch-stock.sh AAPL` |
| `fetch-stocks.sh` | 주요 주식 일괄 | `fetch-stocks.sh` |
| `fetch-crypto.sh` | 단일 암호화폐 | `fetch-crypto.sh bitcoin` |
| `fetch-cryptos.sh` | 주요 암호화폐 일괄 | `fetch-cryptos.sh` |
| `fetch-exchange.sh` | 환율 조회 | `fetch-exchange.sh USD KRW` |

## 실시간 데이터 (스킬 로드 시 자동 조회)

### 주요 암호화폐 현재가
!`bash "$CLAUDE_PROJECT_DIR/scripts/finance/fetch-cryptos.sh" 2>/dev/null || echo "[]"`

### USD/KRW 환율
!`bash "$CLAUDE_PROJECT_DIR/scripts/finance/fetch-exchange.sh" USD KRW 2>/dev/null || echo "{}"`

## 추가 데이터 조회 방법

사용자가 특정 종목이나 코인을 요청하면 다음 명령을 실행하세요:

```bash
# 주식 시세 조회
bash "$CLAUDE_PROJECT_DIR/scripts/finance/fetch-stock.sh" <SYMBOL>
# 예: AAPL, MSFT, GOOGL, TSLA, 005930.KS (삼성전자)

# 암호화폐 시세 조회
bash "$CLAUDE_PROJECT_DIR/scripts/finance/fetch-crypto.sh" <COIN_ID>
# 예: bitcoin, ethereum, solana, ripple, dogecoin

# 환율 조회
bash "$CLAUDE_PROJECT_DIR/scripts/finance/fetch-exchange.sh" <FROM> <TO>
# 예: USD KRW, EUR USD, JPY KRW
```

## 응답 가이드라인

1. **간결하게**: 핵심 데이터만 제공
2. **가격 포맷**: 통화 기호 포함 (₿, $, ₩)
3. **변동률**: 상승(📈), 하락(📉) 이모지 사용
4. **한국어**: 사용자가 한국어로 질문하면 한국어로 응답

## A2UI 응답 형식 (Finance Agent 서버용)

Finance Agent 서버에서 호출될 때는 A2UI JSONL 형식으로 응답합니다:

```jsonl
{"surfaceUpdate":{"components":[{"type":"Text","id":"price_info","text":"**비트코인 (BTC)**\n현재가: $97,000 📉 -2.5%\n24시간 거래량: $45B"}]}}
{"beginRendering":{"surfaceId":"main","componentId":"price_info"}}
```

$ARGUMENTS
