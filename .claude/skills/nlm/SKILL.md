---
name: nlm
description: "NLM 세컨드 브레인 — 노트북 조회, 학습 기록, 경험 축적. 키워드: NLM, 세컨드 브레인, second brain, 노트북, notebook, 학습, 교훈, lesson, 경험, knowledge"
allowed-tools: Bash(nlm:*), Bash(python3:*), Bash(cat:*), Read, Write
---

# NLM Second Brain (세컨드 브레인)

## 개요

NLM(NotebookLM)은 마이클의 **장기 기억 시스템**이다.
세션이 바뀌어도 유지되는 **영구적 지식 저장소**로, 과거 경험·교훈·분석 결과를 축적한다.

- **Source**: 참고 자료 (API 문서, 코드베이스 등) — 읽기 전용 지식
- **Note**: 학습 기록 (성공/실패 경험, 교훈) — CRUD 가능
- **Query**: 자연어 질문으로 축적된 지식 검색

## nlm CLI 명령어

### 노트북 조회

```bash
# 노트북 목록 (data/nlm-notebooks.json 파일 참조)
cat data/nlm-notebooks.json | python3 -m json.tool

# 노트북 개요
nlm describe notebook <notebook_id>
```

### 질의 (Query) — 작업 전 반드시 실행

```bash
# 특정 노트북에 질문
nlm notebook query <notebook_id> "질문 내용"

# 예시: Polymarket 거래 경험 조회
nlm notebook query c4c42932-5266-421c-9657-deb50b38515d "Gamma API 사용 시 주의사항은?"

# 예시: Binance 경험 조회
nlm notebook query 766109ef-af97-4ed3-a1a8-9ce9e14a9c14 "선물 포지션 value_usd 계산법은?"

# 예시: 마이클 메인 노트북
nlm notebook query c3cebd51-e260-4de4-9a57-a9cc9913dd4c "최근 학습한 교훈은?"
```

### Note CRUD — 학습 기록

```bash
# Note 생성 (경험/교훈 기록)
nlm note create <notebook_id> --title "[SUCCESS] 2026-02-16: 제목" --content "상세 내용"
nlm note create <notebook_id> --title "[FAILURE] 2026-02-16: 제목" --content "원인과 해결 방법"

# Note 목록 조회
nlm note list <notebook_id> --json

# Note 수정
nlm note update <notebook_id> <note_id> --content "수정된 내용" --title "수정된 제목"

# Note 삭제
nlm note delete <notebook_id> <note_id> --confirm
```

### Source 관리 — 참고 자료

```bash
# Source 목록
nlm source list <notebook_id> --json

# 텍스트 Source 추가
nlm source add <notebook_id> --text "내용" --title "제목" --wait

# 파일 Source 추가
nlm source add <notebook_id> --file /path/to/file.md --wait

# Source 삭제
nlm source delete <source_id> --confirm
```

## 주요 노트북

| 노트북 | ID | 용도 |
|--------|-----|------|
| **michael** | `c3cebd51-e260-4de4-9a57-a9cc9913dd4c` | 메인 (종합 지식) |
| **binance_trader** | `766109ef-af97-4ed3-a1a8-9ce9e14a9c14` | Binance 거래 경험 |
| **pm_trader** | `c4c42932-5266-421c-9657-deb50b38515d` | Polymarket 거래 경험 |
| **portfolio** | `36e85c3c-f11d-4206-bc75-cd975849f749` | 포트폴리오 관리 |
| **risk** | `195aa81f-1931-4267-a014-8aa90d6b2f7d` | 리스크 관리 |
| **pm_scanner** | `45681010-30ad-4731-876d-c1a15456fc70` | PM 마켓 스캔 |
| **market_data** | `4ce38aeb-1b53-40d4-8913-4af09a612f13` | 시장 데이터 |
| **technical** | `88c531e7-b1d1-4653-acda-bdd848c49017` | 기술 분석 |
| **rebalancer** | `bf8efc50-298c-444f-9a93-52af6c6c54de` | 리밸런싱 전략 |

전체 목록: `data/nlm-notebooks.json`

## 활용 원칙

### 1. 작업 전 Query (Pull before Act)
작업을 시작하기 전에 관련 노트북에 query하여 과거 경험을 확인한다.
```
Polymarket 거래 → pm_trader 노트북 query
Binance 거래 → binance_trader 노트북 query
포트폴리오 점검 → portfolio 노트북 query
```

### 2. 경험 즉시 기록 (Write after Learn)
성공/실패 경험은 즉시 Note로 기록한다.
- 제목 형식: `[SUCCESS|FAILURE] YYYY-MM-DD: 간략 설명`
- 내용: 원인, 과정, 결과, 교훈

### 3. 노트북 선택 기준
- **거래 실행** 관련 → `binance_trader` 또는 `pm_trader`
- **분석/전략** 관련 → `portfolio`, `risk`, `rebalancer`
- **데이터/스캔** 관련 → `market_data`, `pm_scanner`, `technical`
- **범용/기타** → `michael`

### 4. [LESSON:] 마커 (자동 기록)
응답에 `[LESSON:제목:내용]` 마커를 포함하면 자동으로 michael 노트북에 Note가 생성된다.

### 5. 30일 자동 정리
매주 일요일 03:00에 30일 초과 Note가 자동 삭제된다.
중요한 교훈은 Source로 승격하여 영구 보존한다.

## 헬퍼 스크립트

```bash
# 전체 노트북 상태 조회
python3 .claude/skills/nlm/scripts/nlm_status.py

# 특정 노트북 질의
python3 .claude/skills/nlm/scripts/nlm_query.py <agent_name> "질문"
```
