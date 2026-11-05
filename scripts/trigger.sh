#!/usr/bin/env bash
# 비서컴(상시 가동 Mac) → GitHub Actions workflow_dispatch 호출기.
# GitHub 예약(schedule)은 지연·누락이 잦으므로, 정시에 이 스크립트가 dispatch를 '즉시 실행'으로 호출한다.
# 네트워크 일시 장애 대비 재시도(최대 약 30분). 최종 실패해도 GitHub 예약 슬롯이 백업으로 남는다.
#
# 사용: trigger.sh <workflow-file>
#   예) trigger.sh daily-email.yml   /   trigger.sh daily-collect.yml
set -uo pipefail

WF="${1:?workflow 파일명 필요 (예: daily-email.yml)}"
REPO="supernewt2504/game-market-research"
LOG="${HOME}/Library/Logs/game-market-trigger.log"

# launchd는 최소 PATH로 실행 → gh 경로를 직접 탐색(Apple Silicon Homebrew 우선)
GH="$(command -v gh || true)"
[ -z "$GH" ] && [ -x "$HOME/bin/gh" ]        && GH="$HOME/bin/gh"
[ -z "$GH" ] && [ -x "$HOME/.local/bin/gh" ] && GH="$HOME/.local/bin/gh"
[ -z "$GH" ] && [ -x /opt/homebrew/bin/gh ]  && GH=/opt/homebrew/bin/gh
[ -z "$GH" ] && [ -x /usr/local/bin/gh ]     && GH=/usr/local/bin/gh

mkdir -p "$(dirname "$LOG")"
ts(){ date '+%F %T %Z'; }

# 토큰 파일이 있으면 GH_TOKEN 으로 사용(launchd에서 키체인 접근 없이 동작). 없으면 gh 자체 인증(keychain) 사용.
[ -f "$HOME/.config/gh-token" ] && export GH_TOKEN="$(tr -d '[:space:]' < "$HOME/.config/gh-token")"

if [ -z "$GH" ]; then
  echo "[$(ts)] ERROR: gh CLI 없음 — 'brew install gh' 후 'gh auth login' 필요 ($WF)" >> "$LOG"
  exit 127
fi

echo "[$(ts)] dispatch 시도: $WF" >> "$LOG"
for i in $(seq 1 10); do
  if "$GH" workflow run "$WF" --repo "$REPO" >> "$LOG" 2>&1; then
    echo "[$(ts)] dispatch 성공: $WF (시도 $i/10)" >> "$LOG"
    exit 0
  fi
  echo "[$(ts)] dispatch 실패 — 재시도 $i/10 (180초 후)" >> "$LOG"
  sleep 180
done

echo "[$(ts)] dispatch 최종 실패: $WF — GitHub 예약 백업에 의존" >> "$LOG"
exit 1
