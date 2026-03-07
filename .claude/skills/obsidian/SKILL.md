---
name: obsidian
description: |
  Obsidian Vault 지식 저장소 관리 스킬.
  키워드: obsidian, vault, 노트, 지식, knowledge, playbook, journal, 저널, 리뷰
allowed-tools: Bash(bash:*), Read, Write, Glob, Grep
---

# Obsidian Vault — 영구 지식 저장소

## 개요

Obsidian vault는 마이클의 **영구 지식 저장소**. NLM의 30일 TTL 한계를 보완하여:
- NLM 교훈의 영구 보존
- 구조화된 지식 관리 (디렉토리, 태그, 프론트매터)
- 사람이 직접 편집/큐레이션 가능
- Git 버전 관리 가능

## Vault 경로

```
OBSIDIAN_VAULT_PATH (기본: data/obsidian-vault/)
```

## 디렉토리 구조

```
{vault}/
├── daily/          # 일일 트레이딩 저널 (YYYY-MM-DD.md)
├── weekly/         # 주간 리뷰 (YYYY-WNN.md)
├── playbooks/      # 전략 플레이북 (영구, 큐레이션됨)
├── lessons/        # NLM에서 아카이빙된 교훈
│   ├── binance/
│   ├── polymarket/
│   └── general/
├── analysis/       # 시장 분석 노트
├── portfolio/      # 포트폴리오 스냅샷
├── templates/      # 노트 템플릿
└── _index.md       # Vault 개요 (MOC)
```

## 프론트매터 형식

모든 노트는 YAML 프론트매터 필수:

```yaml
---
title: "노트 제목"
date: "2026-02-16"
type: daily | weekly | lesson | playbook | analysis | portfolio
domain: binance | polymarket | portfolio | risk | general
tags: [tag1, tag2]
source: nlm | manual | auto-generated
nlm_notebook: binance_trader  # (선택) 원본 NLM 노트북명
nlm_note_id: uuid             # (선택) 원본 NLM 노트 ID
status: active | archived | draft
---
```

## 사용 패턴

### 1. 교훈 직접 기록

```bash
# vault 디렉토리에 직접 마크다운 파일 생성
cat > data/obsidian-vault/lessons/binance/hedge-mode-lesson.md << 'EOF'
---
title: "Hedge Mode positionSide 필수"
date: "2026-02-16"
type: lesson
domain: binance
tags: [futures, hedge-mode]
source: manual
status: active
---

# Hedge Mode positionSide 필수

Binance Futures에서 Hedge mode 활성화 시, 모든 주문에 positionSide (LONG/SHORT) 파라미터 필수.
생략 시 -4061 에러.
EOF
```

### 2. 플레이북 생성/편집

```bash
# 큐레이션된 전략 플레이북
cat > data/obsidian-vault/playbooks/btc-dip-buying.md << 'EOF'
---
title: "BTC Dip Buying Strategy"
date: "2026-02-16"
type: playbook
domain: binance
tags: [btc, dip-buying, strategy]
source: manual
status: active
---

# BTC Dip Buying Strategy

## Entry
- RSI < 30 on 4H chart
- Price drops > 5% in 24h

## Position
- 5% of portfolio per entry
- Max 3 entries per dip

## Exit
- TP: +10% from entry
- SL: -5% from entry
EOF
```

### 3. 노트 검색

```bash
# 키워드로 검색 (grep)
grep -rl "Hedge mode" data/obsidian-vault/lessons/

# 프론트매터로 필터
grep -rl "domain: binance" data/obsidian-vault/ --include="*.md"

# 활성 플레이북만
grep -rl "status: active" data/obsidian-vault/playbooks/
```

## 자동 동기화 (Cron)

| 스케줄 | 작업 |
|--------|------|
| 매일 21:00 UTC | 일일 저널 자동 생성 |
| 일요일 02:00 UTC | 주간 리뷰 자동 생성 |
| 일요일 02:30 UTC | NLM→Vault 교훈 아카이빙 |
| 매일 03:30 UTC | Vault→NLM 플레이북 업로드 |

## NLM과의 관계

```
NLM (AI 질의 엔진, 30일 TTL)
  ↕ 양방향 동기화
Obsidian Vault (영구 저장소, 구조화)
```

- **NLM→Vault**: 교훈 자동 아카이빙 (30일 삭제 전 영구 보존)
- **Vault→NLM**: 큐레이션된 플레이북을 NLM Source로 업로드 (AI 품질 향상)
- **[LESSON:]**: 마커 발견 시 NLM + Vault 동시 기록 (듀얼 라이트)

## 핵심 교훈

1. Vault는 "마크다운 파일 폴더"일 뿐 — Obsidian 앱 불필요
2. 프론트매터가 메타데이터 — 반드시 포함
3. 플레이북은 `status: active`만 NLM에 업로드
4. `nlm_note_id`로 중복 아카이빙 방지
