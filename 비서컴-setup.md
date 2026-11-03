# 비서컴 안정화 발송 — 설치 가이드

GitHub 예약(cron)의 지연·누락을 없애기 위해, **상시 가동 비서컴(M1 Pro)**이 매일 정시에
GitHub Actions를 `workflow_dispatch`(즉시 실행)로 호출한다.

- **비서컴은 수집/발송을 직접 하지 않는다.** 실제 파이프라인(수집→조사→리포트→메일)은 전부 GitHub 러너에서 돈다.
  비서컴은 "버튼만 정시에 누르는" 역할 → 필요 프로그램은 `gh` 하나뿐(Node·Python·API키·SMTP 불필요).
- **이중 안전망**: 비서컴 호출(주) + 기존 GitHub 예약 cron(보조). 둘이 겹쳐도
  발송은 마커(`last_emailed.txt`), 수집은 신선도 멱등성으로 **하루 1회만** 실행 → 중복 없음.

타이머(KST):
| 작업 | 시각 | 호출 대상 |
|---|---|---|
| 수집 | 23:45 | `daily-collect.yml` |
| 발송 | 08:00 | `daily-email.yml` |

---

## 사전 조건 (비서컴에서 1회)

### 1. gh 설치 + 인증
```bash
brew install gh
gh auth login          # GitHub 계정, HTTPS, 이 repo workflow 실행 권한
gh auth status         # 로그인 확인
```
- 인증 토큰은 비서컴 밖으로 나가지 않는다.
- (대안) 무인 안정성을 위해 세분화 PAT를 쓰려면: repo `game-market-research` / 권한 **Actions: Read and write**로 발급 후
  `echo <PAT> | gh auth login --with-token`.
- 만료형 PAT를 쓸 경우 만료일 캘린더 알림 필수(만료 시 호출 거부됨).

### 2. 저장소 클론 (스크립트 사용)
```bash
git clone https://github.com/supernewt2504/game-market-research.git
cd game-market-research
```

### 3. 절전 OFF (가장 중요)
"24시간 켜짐"이어도 macOS가 자동으로 자면 그 시각에 안 뜬다.
```bash
sudo pmset -a sleep 0 displaysleep 0 disablesleep 1
pmset -g | grep -E 'sleep|disablesleep'   # 확인
```
(또는 시스템 설정 > 에너지 > "자동으로 잠자기 방지".)

### 4. 자동 로그인 ON
LaunchAgent는 사용자 로그인 세션에서 실행된다. 재부팅(정전 등) 후에도 자동 복구되도록
시스템 설정 > 사용자 및 그룹 > 자동 로그인 = 해당 계정.

### 5. 시간대 확인
```bash
sudo systemsetup -gettimezone     # Asia/Seoul 이어야 함
```

---

## 설치
```bash
bash scripts/install_triggers.sh
```

## 확인 / 운영
```bash
launchctl list | grep gamemarket            # 타이머 2개 등록 확인
tail -f ~/Library/Logs/game-market-trigger.log   # 호출 로그
bash scripts/trigger.sh daily-email.yml     # 수동 테스트(당일 이미 보냈으면 멱등 skip)
```
GitHub에서 실제 실행 확인:
```bash
gh run list --workflow=daily-email.yml -L 5
gh run list --workflow=daily-collect.yml -L 5
```

## 변경/제거
- 시각 변경: `scripts/install_triggers.sh`의 `make_plist` 시·분 수정 후 재실행.
- 제거:
```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/co.supernewt.gamemarket.collect.plist
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/co.supernewt.gamemarket.email.plist
rm ~/Library/LaunchAgents/co.supernewt.gamemarket.*.plist
```

---

## 남는 약점과 대응
| 약점 | 대응 |
|---|---|
| 비서컴 꺼짐/정전 | GitHub 예약 cron이 백업으로 늦게라도 발송(마커로 중복 방지) |
| 집 인터넷 끊김 | trigger.sh 30분 재시도 + GitHub cron 백업 |
| gh 토큰 만료 | `gh auth`(갱신형) 사용 또는 PAT 만료 알림 |
| 절전/로그아웃 | 위 3·4번 설정으로 차단 |
