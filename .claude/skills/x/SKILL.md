---
name: x-twitter
description: |
  X (Twitter) 검색 및 조회 스킬. 사용자 프로필, 트윗 검색, 트렌딩 확인.
  다음 질문에 사용: "트위터", "X", "트윗", "일론 머스크", "트렌딩", "팔로워"
allowed-tools: Bash, Read
---

# X (Twitter) Skill

## 빠른 URL 패턴

### 프로필 접근
```
https://x.com/{username}              # 프로필 페이지
https://x.com/{username}/status/{id}  # 특정 트윗
https://x.com/{username}/followers    # 팔로워 목록
https://x.com/{username}/following    # 팔로잉 목록
https://x.com/{username}/likes        # 좋아요한 트윗
```

### 검색
```
https://x.com/search?q={query}&src=typed_query  # 일반 검색
https://x.com/search?q=from:{username}          # 특정 사용자 트윗만
https://x.com/search?q={query}&f=live           # 최신순
https://x.com/search?q={query}&f=user           # 사용자 검색
https://x.com/search?q={query}&f=image          # 이미지 포함
https://x.com/search?q={query}&f=video          # 비디오 포함
```

### 트렌딩 & 탐색
```
https://x.com/explore              # 탐색
https://x.com/explore/tabs/for-you # 트렌딩
https://x.com/explore/tabs/trending # 트렌딩 (대체)
https://x.com/notifications        # 알림
https://x.com/home                 # 홈 타임라인
```

## 로그인 정보

### 계정
- **사용자 아이디**: idongmyeon67121
- **이름**: 이동명
- **이메일**: ldmprog@gmail.com

### 로그인 플로우 (Playwright)
1. `https://x.com/home` 또는 `https://x.com/login` 접속
2. 로그인 다이얼로그 대기 (2초)
3. 사용자 아이디 입력 → "다음" 클릭
4. 비밀번호 입력 → "로그인하기" 클릭
5. 홈 타임라인 로드 확인

## 검색 연산자

| 연산자 | 설명 | 예시 |
|--------|------|------|
| `from:` | 특정 사용자의 트윗 | `from:elonmusk` |
| `to:` | 특정 사용자에게 보낸 트윗 | `to:elonmusk` |
| `@` | 멘션 포함 | `@tesla` |
| `#` | 해시태그 | `#BTS` |
| `since:` | 특정 날짜 이후 | `since:2024-01-01` |
| `until:` | 특정 날짜 이전 | `until:2024-12-31` |
| `min_retweets:` | 최소 리트윗 수 | `min_retweets:1000` |
| `min_faves:` | 최소 좋아요 수 | `min_faves:5000` |
| `filter:links` | 링크 포함 | `filter:links` |
| `filter:images` | 이미지 포함 | `filter:images` |
| `filter:videos` | 비디오 포함 | `filter:videos` |
| `-filter:replies` | 답글 제외 | `-filter:replies` |
| `lang:` | 언어 필터 | `lang:ko` |

### 고급 검색 예시
```
# 일론 머스크의 최근 인기 트윗 (답글 제외)
from:elonmusk -filter:replies min_faves:10000

# BTS 관련 한국어 트윗 (이미지 포함)
#BTS lang:ko filter:images

# 특정 기간 Tesla 관련
Tesla since:2024-01-01 until:2024-06-30
```

## Playwright 자동화 팁

### 페이지 로딩 대기
- 초기 로딩: 2-3초
- 스크롤 후 콘텐츠 로딩: 1-2초
- 로그인 후 리다이렉트: 2-3초

### 요소 참조 (ref) 패턴
- 탭 전환: `tab "Posts"`, `tab "Replies"`, `tab "Media"`
- 트윗 작성: `textbox "Post text"`
- 검색: `combobox "Search query"`

### 주의사항
1. Google 로그인 팝업은 별도 탭에서 열림 → 탭 전환 필요
2. 무한 스크롤 → `End` 키 또는 스크롤로 더 로드
3. 리포스트 vs 본인 트윗 구분 필요 ("reposted" 텍스트 확인)

## 자주 검색하는 계정

| 계정 | 사용자명 | 분야 |
|------|----------|------|
| Elon Musk | @elonmusk | Tech/SpaceX/Tesla |
| BTS | @BTS_twt | K-pop |
| BIGHIT MUSIC | @BIGHIT_MUSIC | Entertainment |
| Netflix Korea | @NetflixKR | Entertainment |
| Tesla | @Tesla | EV/Energy |
| SpaceX | @SpaceX | Aerospace |

## 트윗 작성 (Post)

### 트윗 작성 URL
```
https://x.com/compose/post      # 트윗 작성 다이얼로그 열기
https://x.com/intent/tweet?text={내용}  # 텍스트 미리 채움
```

### Playwright 트윗 작성 플로우
```
1. https://x.com/compose/post 접속
2. 다이얼로그 로딩 대기 (2초)
3. textbox "Post text" 에 내용 입력
   - browser_type(ref, text)
4. "Post" 버튼 클릭
   - button "Post" (텍스트 입력 전 disabled 상태)
5. 게시 완료 확인
```

### 트윗 작성 UI 요소

| 요소 | Playwright ref | 설명 |
|------|----------------|------|
| 텍스트 입력 | `textbox "Post text"` | 트윗 내용 입력란 |
| 게시 버튼 | `button "Post"` | 텍스트 입력 시 활성화 |
| 닫기 | `button "Close"` | 다이얼로그 닫기 |
| 임시저장 | `button "Drafts"` | 임시저장 목록 |
| 공개범위 | `button "Everyone can reply"` | 답글 허용 범위 설정 |

### 첨부 기능

| 기능 | 버튼 | 사용법 |
|------|------|--------|
| 사진/동영상 | `button "Add photos or video"` | 클릭 후 파일 선택 |
| GIF | `button "Add a GIF"` | GIF 검색 다이얼로그 |
| Grok 향상 | `button "Enhance your post with Grok"` | AI로 트윗 개선 |
| 투표 | `button "Add poll"` | 투표 옵션 추가 |
| 이모지 | `button "Add emoji"` | 이모지 선택기 |
| 예약 게시 | `button "Schedule post"` | 예약 시간 설정 |
| 위치 태그 | `button "Tag location"` | (비활성화 상태) |

### 트윗 작성 예시 코드 (Playwright)
```javascript
// 1. 트윗 작성 페이지 열기
await browser_navigate({ url: 'https://x.com/compose/post' });

// 2. 로딩 대기
await browser_wait_for({ time: 2 });

// 3. 텍스트 입력
await browser_type({
  ref: 'e88',  // textbox "Post text"
  text: '안녕하세요! 첫 번째 자동 트윗입니다. #test'
});

// 4. 게시 버튼 클릭
await browser_click({
  ref: 'e150',  // button "Post"
  element: 'Post 버튼'
});
```

### 트윗 작성 시 주의사항
1. **글자 수 제한**: 280자 (한글 포함)
2. **Post 버튼**: 텍스트 입력 전까지 `disabled` 상태
3. **ref 값 변동**: 페이지 로드마다 ref가 달라질 수 있음 → `textbox "Post text"` 등 역할로 찾기
4. **미디어 업로드**: `browser_file_upload` 사용
5. **연속 게시 제한**: 스팸 방지로 빠른 연속 게시 시 제한될 수 있음

### 답글 작성
```
1. 트윗 상세 페이지 접속: https://x.com/{username}/status/{id}
2. 답글 입력란 찾기: textbox "Post your reply"
3. 내용 입력 후 "Reply" 버튼 클릭
```

### 인용 트윗 (Quote)
```
1. 원본 트윗에서 "Repost" 버튼 클릭
2. "Quote" 옵션 선택
3. 인용 코멘트 작성 후 게시
```

## 트러블슈팅

### 로그인 실패 시
1. 쿠키/세션 만료 → 재로그인
2. Google 팝업 닫힘 → 다시 시도
3. CAPTCHA 발생 → 수동 개입 필요

### 콘텐츠 로드 안 될 때
1. `browser_wait_for` 시간 늘리기
2. 페이지 새로고침
3. 네트워크 상태 확인

### 트윗 작성 실패 시
1. 로그인 상태 확인
2. 글자 수 제한 (280자) 확인
3. 네트워크 연결 상태 확인
4. 스팸 방지 제한 여부 확인

$ARGUMENTS
