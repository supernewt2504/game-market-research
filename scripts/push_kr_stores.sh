#!/usr/bin/env bash
# 비서컴 전용: 당일(원스토어·갤럭시) OCR 랭킹을 repo 포맷으로 변환해 커밋·푸시.
# launchd 로 매일 23:30 KST 실행(기존 23:45 collect dispatch 직전). GitHub daily-collect 가
# data/kr_stores/<date>.json 을 스냅샷에 병합한다. 입력 파일(~/secretary/out/rank)이 없으면 조용히 생략.
set -uo pipefail

REPO="${GMR_REPO:-$HOME/game-market-research}"
DATE="$(TZ=Asia/Seoul date +%F)"
LOG="$HOME/Library/Logs/game-market-krstores.log"
PY="$(command -v python3 || echo /usr/bin/python3)"
ts(){ date '+%F %T %Z'; }
mkdir -p "$(dirname "$LOG")"

# 토큰 파일이 있으면 GH_TOKEN 으로 사용(launchd에서 키체인 없이 git push 가능).
[ -f "$HOME/.config/gh-token" ] && export GH_TOKEN="$(tr -d '[:space:]' < "$HOME/.config/gh-token")"

# GH_TOKEN 있으면 그 토큰으로, 없으면 git 기본 자격증명으로 push.
git_push() {
  if [ -n "${GH_TOKEN:-}" ]; then
    git -c credential.helper= \
        -c credential.helper='!f(){ test "$1" = get && printf "username=x-access-token\npassword=%s\n" "$GH_TOKEN"; }; f' \
        push -q origin HEAD:main
  else
    git push -q origin HEAD:main
  fi
}

cd "$REPO" 2>/dev/null || { echo "[$(ts)] repo 없음: $REPO" >> "$LOG"; exit 1; }
# 커밋 신원(로컬에 없으면 설정)
git config user.email >/dev/null 2>&1 || git config user.email "dragonewt@supernewt.co.kr"
git config user.name  >/dev/null 2>&1 || git config user.name  "secretary-m1"

git pull --rebase --autostash -q origin main >> "$LOG" 2>&1 || true

if ! "$PY" scripts/import_kr_stores.py "$DATE" >> "$LOG" 2>&1; then
  echo "[$(ts)] import 실패(수집 실패일로 간주) $DATE — 생략" >> "$LOG"
  exit 0
fi

if [ -z "$(git status --porcelain data/kr_stores/)" ]; then
  echo "[$(ts)] 변경 없음 $DATE" >> "$LOG"
  exit 0
fi

git add "data/kr_stores/$DATE.json" "data/kr_stores/_icons.json"
git commit -q -m "kr-stores: 원스토어·갤럭시 $DATE (아이콘 포함) [skip ci]" >> "$LOG" 2>&1
for i in 1 2 3; do
  git pull --rebase --autostash -q origin main >> "$LOG" 2>&1 \
    && git_push >> "$LOG" 2>&1 \
    && { echo "[$(ts)] push 성공 $DATE" >> "$LOG"; exit 0; }
  echo "[$(ts)] push 재시도 $i/3" >> "$LOG"; sleep 10
done
echo "[$(ts)] push 최종 실패 $DATE" >> "$LOG"
exit 1
