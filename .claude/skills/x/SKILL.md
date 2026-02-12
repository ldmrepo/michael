---
name: x-twitter
description: |
  X (Twitter) 검색/조회/트윗 작성/팔로우 스킬. Playwright 브라우저 자동화.
  다음 질문에 사용: "트위터", "X", "트윗", "일론 머스크", "트렌딩", "팔로워", "게시", "포스트"
allowed-tools: Bash, Read
---

# X (Twitter) Skill

## 계정 정보

| 항목 | 값 |
|------|-----|
| 사용자 아이디 | `@idongmyeon67121` |
| 이름 | 이동명 |
| 이메일 | ldmprog@gmail.com |
| Bio | Software Developer \| Building AI Agents & Web3 apps \| TypeScript & Python \| Sharing dev experiences and hard-won lessons |
| Location | Seoul, South Korea |
| 프로필 URL | https://x.com/idongmyeon67121 |

## 팔로잉 개발자 (2026-02-12 설정)

| 계정 | 분야 |
|------|------|
| @karpathy | AI/Deep Learning, ex-Tesla/OpenAI |
| @rauchg | Vercel CEO, Next.js |
| @youyuxi | Vue.js/Vite 창시자 |
| @dan_abramov | React 코어팀 |
| @addyosmani | Google Chrome 엔지니어링 |
| @levelsio | 인디 해커 (Nomad List, Photo AI) |
| @ThePrimeagen | 개발자 콘텐츠, ex-Netflix |
| @kentcdodds | React/Testing 교육 |
| @swyx | DX 엔지니어, AI/웹 |
| @t3dotgg | T3 스택, TypeScript 풀스택 |
| @elonmusk | (기본 팔로우) |

## URL 패턴

### 프로필/트윗
```
https://x.com/{username}              # 프로필
https://x.com/{username}/status/{id}  # 특정 트윗
https://x.com/{username}/followers    # 팔로워
https://x.com/{username}/following    # 팔로잉
https://x.com/home                    # 홈 타임라인
https://x.com/explore                 # 탐색/트렌딩
https://x.com/notifications           # 알림
```

### 검색
```
https://x.com/search?q={query}&src=typed_query  # 일반 검색
https://x.com/search?q=from:{username}          # 특정 사용자
https://x.com/search?q={query}&f=live           # 최신순
https://x.com/search?q={query}&f=user           # 사용자 검색
```

## 트윗 작성 (CRITICAL - 실전 검증)

### 권장 방법: 홈 페이지 인라인 작성

> **IMPORTANT**: `/compose/post` 사용 금지! 파일 선택 모달이 누적되어 Playwright 스냅샷이 빈 화면 반환.

```
1. https://x.com/home 접속
2. "게시물 본문" 텍스트박스 대기 (waitFor "게시하기")
3. 텍스트박스 클릭 (textbox "게시물 본문")
4. browser_type()으로 내용 입력
5. "게시하기" 버튼 클릭
```

### data-testid 셀렉터 (안정적)

| 요소 | data-testid | 설명 |
|------|-------------|------|
| 트윗 텍스트박스 | `tweetTextarea_0` | 인라인 작성 영역 |
| 게시 버튼 (인라인) | `tweetButtonInline` | 홈 페이지 게시 버튼 |
| 팔로우 버튼 | `{userId}-follow` | 프로필 팔로우 버튼 |
| 언팔로우 버튼 | `{userId}-unfollow` | 프로필 언팔로우 |

### 게시 버튼 클릭 시 오버레이 차단 대응

게시 버튼이 `layers` div에 의해 차단될 경우 JavaScript로 직접 클릭:

```javascript
// Escape로 오버레이 닫기 시도
await page.keyboard.press('Escape');

// 그래도 안 되면 JavaScript 직접 클릭
await page.evaluate(() => {
  document.querySelector('[data-testid="tweetButtonInline"]').click();
});
```

### 글자 수 확인

- 280자 제한 (한글 포함)
- 입력 후 스냅샷에서 "N 글자수 남아있는" 텍스트로 잔여 글자 확인
- 해시태그는 자동 링크로 변환됨 (글자 수에 포함)

## 팔로우 자동화

### 단일 팔로우
```
1. https://x.com/{username} 접속
2. "팔로우" 텍스트 대기
3. button "팔로우 @{username}" 클릭
4. "팔로잉" 표시 확인
```

### 대량 팔로우 (Playwright run_code)
```javascript
async (page) => {
  const devs = ['karpathy', 'rauchg', 'youyuxi'];
  const results = [];
  for (const dev of devs) {
    await page.goto(`https://x.com/${dev}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    const btn = page.locator('[data-testid$="-follow"]').first();
    if (await btn.isVisible({ timeout: 5000 })) {
      const text = await btn.textContent();
      if (text?.includes('팔로우') && !text?.includes('팔로잉')) {
        await btn.click();
        await page.waitForTimeout(1000);
        results.push(`${dev}: followed`);
      } else {
        results.push(`${dev}: already following`);
      }
    }
  }
  return results;
}
```

## 한국어 UI 요소 매핑

| 영어 | 한국어 | 비고 |
|------|--------|------|
| Post | 게시하기 | 트윗 게시 버튼 |
| Post text | 게시물 본문 | 트윗 입력란 |
| Follow | 팔로우 | 팔로우 버튼 |
| Following | 팔로잉 | 이미 팔로우 중 |
| Reply | 답글 | 답글 탭/버튼 |
| Repost | 재게시 | 리트윗 |
| Like | 마음에 들어요 | 좋아요 |
| Bookmark | 북마크 | 저장 |
| Search | 검색 및 탐색 | 검색 메뉴 |
| Home | 홈 | 홈 메뉴 |
| Profile | 프로필 | 프로필 메뉴 |
| Edit profile | 프로필 수정 | 프로필 편집 |

## 검색 연산자

| 연산자 | 설명 | 예시 |
|--------|------|------|
| `from:` | 특정 사용자의 트윗 | `from:elonmusk` |
| `to:` | 특정 사용자에게 보낸 트윗 | `to:elonmusk` |
| `since:` | 특정 날짜 이후 | `since:2026-01-01` |
| `until:` | 특정 날짜 이전 | `until:2026-12-31` |
| `min_retweets:` | 최소 리트윗 수 | `min_retweets:1000` |
| `min_faves:` | 최소 좋아요 수 | `min_faves:5000` |
| `filter:links` | 링크 포함 | |
| `filter:images` | 이미지 포함 | |
| `filter:videos` | 비디오 포함 | |
| `-filter:replies` | 답글 제외 | |
| `lang:` | 언어 필터 | `lang:ko` |

## 실전 교훈 (CRITICAL)

1. **`/compose/post` 사용 금지**: 파일 선택 모달 ~15개 누적 → 스냅샷 빈 화면 → 브라우저 재시작 필요
2. **홈 페이지 인라인 작성 사용**: `x.com/home` → 텍스트박스 클릭 → 입력 → 게시
3. **`fill()` = 덮어쓰기**: browser_type의 fill()은 기존 텍스트를 교체 (append 아님). 빈 텍스트박스에서 시작하면 정상 동작
4. **오버레이 차단**: "게시하기" 버튼 클릭 시 `layers` div가 차단할 수 있음 → Escape 또는 JS 직접 클릭
5. **프로필 설정 순서**: 프로필 수정 → Bio → Location → Save (아바타/헤더는 Skip 가능)
6. **팔로우 버튼 셀렉터**: `[data-testid$="-follow"]`로 안정적 매칭. 텍스트 "팔로잉" 포함 시 이미 팔로우 중

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 스냅샷 빈 화면 | 파일 선택 모달 누적 | `browser_close` → 새 세션 |
| 게시 버튼 클릭 안 됨 | layers div 오버레이 차단 | `Escape` 또는 JS `evaluate()` |
| fill()로 텍스트 추가됨 | 기존 텍스트 위에 append | 브라우저 재시작 후 깨끗한 상태에서 입력 |
| 로그인 필요 | 세션 만료 | 재로그인 (아이디 → 다음 → 비밀번호) |
| CAPTCHA | 자동화 감지 | 수동 개입 필요 |

$ARGUMENTS
