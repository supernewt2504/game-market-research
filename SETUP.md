# 게임시장조사 — 설치 & 배포 가이드

매일 대한민국 Google Play · App Store **게임 인기/매출 Top 100**을 수집해, 전일 대비 변동·NEW·피쳐드·상승이유(기사/이미지/영상)를 담은 HTML 리포트를 **다음날 아침 메일로 발송**하는 시스템입니다.

## 구성

```
scripts/
  collect.mjs         순위 수집 (Apple RSS + Google Play)        [토큰 0]
  enrich.mjs          런칭일자 + 개발사 국적(국기)               [토큰 0]
  research.mjs        상승이유 조사(Haiku+웹검색) + 국적 보완     [여기만 토큰 사용]
  generate_report.py  변동 비교 → 웹/이메일 리포트 생성          [토큰 0]
  send_email.py       SMTP 메일 발송                              [토큰 0]
data/                 스냅샷·메타·조사 캐시(= 과거 이력, git 저장)
docs/                 GitHub Pages(웹 리포트 + 상세 모달)
out/                  이메일용 리포트
.github/workflows/    daily-collect(밤 23:50 KST) / daily-email(아침 08:00 KST)
config.json           설정(상한·임계값·메일·모델 등)
```

**토큰 부담**: 수집·비교·리포트·메일은 전부 스크립트라 토큰 0. **상승이유 조사만** Claude Haiku 5.5를 쓰며, 하루 대상은 `max_research_per_day`(기본 15개)로 상한, 상위 유지 게임은 캐시로 재조사하지 않음 → 월 수천 원 수준.

---

## 1) 로컬 테스트 (선택)

```bash
npm install
DATE=$(TZ=Asia/Seoul date +%F)
node scripts/collect.mjs
node scripts/enrich.mjs "$DATE"
node scripts/research.mjs "$DATE"      # API 키 없으면 조사는 자동 생략
python3 scripts/generate_report.py "$DATE"
open docs/daily/$DATE.html
```

API 키/메일 비번을 로컬에서 쓰려면 `.env.example`를 복사해 `.env`로 만들고 값을 채운 뒤 `set -a; . ./.env; set +a` 로 불러옵니다. (`.env`는 git에 올라가지 않습니다.)

---

## 2) Claude API 키 확인/발급

**이미 있는지 확인:** 키 값 자체는 생성 시 한 번만 보이고 다시 볼 수 없습니다. 보유 여부는 콘솔에서 확인합니다.
1. https://console.anthropic.com 로그인
2. 좌측 **API Keys** 메뉴 → 기존 키 목록이 보이면 보유 중(이름/생성일 표시, 값은 안 보임)
3. 값이 필요하면(= 어딘가 저장해둔 게 없으면) **Create Key**로 새로 발급 → `sk-ant-...` 값을 그 자리에서 복사해 안전한 곳에 보관
4. 결제수단이 없으면 **Billing**에서 등록(Haiku는 매우 저렴)

> 조사/국적보완을 안 쓸 거면 키 없이도 동작합니다(모두 "미확인", 국적 일부만 표시).

---

## 3) Gmail(Google Workspace) 앱 비밀번호

발송 계정 **service@supernewt.co.kr** 로 SMTP 발송하려면 "앱 비밀번호"가 필요합니다.
1. 해당 계정에 **2단계 인증** 활성화 (myaccount.google.com → 보안)
2. 보안 → **앱 비밀번호**(App passwords) → 새 비밀번호 생성 → **16자리** 복사
3. 이 값을 아래 `SMTP_PASS` 시크릿에 넣습니다. (일반 로그인 비번 아님)

> Workspace 관리자가 앱 비밀번호를 막아둔 경우: 관리콘솔에서 허용하거나, 대안으로 SMTP relay/OAuth2 방식이 필요합니다(요청 시 안내).

---

## 4) GitHub 저장소 만들고 올리기

```bash
# (이미 git init 완료) 원격 저장소 생성 후:
git add -A
git commit -m "init: 게임시장조사 자동화"
git branch -M main
git remote add origin https://github.com/<사용자명>/game-market-research.git
git push -u origin main
```

> `gh` CLI가 있으면: `gh repo create game-market-research --private --source=. --push`

---

## 5) Secrets / Variables 등록

저장소 → **Settings → Secrets and variables → Actions**

**Secrets (비밀, New repository secret):**
| 이름 | 값 |
|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` (2번에서 발급) |
| `SMTP_USER` | `service@supernewt.co.kr` |
| `SMTP_PASS` | 앱 비밀번호 16자리 (3번) |

**Variables (비밀 아님, Variables 탭):**
| 이름 | 값 |
|---|---|
| `MAIL_TO` | `dragonewt@supernewt.co.kr` (쉼표로 여러 명) |
| `PAGES_BASE_URL` | `https://<사용자명>.github.io/game-market-research` |

---

## 6) GitHub Pages 켜기 (상세 페이지 호스팅)

저장소 → **Settings → Pages** → Source: **Deploy from a branch** → Branch: **main** / 폴더: **/docs** → Save.
몇 분 뒤 `https://<사용자명>.github.io/game-market-research/` 에서 리포트가 열립니다. 이 주소를 5번 `PAGES_BASE_URL`에 넣으면, 메일의 **확인 ▸** 버튼이 이 상세 페이지로 연결됩니다.

---

## 7) 동작 방식 & 수동 실행

- **daily-collect** — 매일 23:50 KST: 수집→비교→조사→리포트 생성→커밋(스냅샷이 과거 이력으로 쌓임)
- **daily-email** — 매일 08:00 KST: 전날 리포트를 메일 발송
- **지금 바로 테스트:** 저장소 → **Actions** 탭 → 워크플로 선택 → **Run workflow**(수동 실행)로 즉시 돌려볼 수 있습니다. 먼저 `daily-collect`를 1회 돌려 첫 스냅샷을 만들고, 다음날 또 돌면 실제 변동 비교가 나옵니다.

> 첫날은 전일 데이터가 없어 변동/상승이유가 비어 있고, **둘째 날부터 실제 전일 대비 비교**가 표시됩니다.

## 설정 바꾸기 (config.json)
- `research.max_research_per_day` 조사 상한(비용 상한)
- `research.rise_threshold` 몇 계단 이상 상승을 조사 대상으로 볼지(기본 5)
- `research.include_popular_charts` 인기순위도 조사할지(기본 true)
- `research.model` 조사 모델(기본 `claude-haiku-5-5`)
- `email.to` 기본 수신자(또는 Variables의 `MAIL_TO`)
