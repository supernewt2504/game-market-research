#!/usr/bin/env bash
# 비서컴에 launchd 타이머 2개 설치:
#   - 수집: 매일 23:45 KST → daily-collect.yml dispatch
#   - 발송: 매일 08:00 KST → daily-email.yml   dispatch
# 멱등: 이미 설치돼 있으면 교체. 비서컴에서 이 repo를 clone한 뒤 한 번만 실행하면 된다.
#   사용: bash scripts/install_triggers.sh
#
# ⚠ 사전 조건(반드시): gh 인증, 절전 OFF, 자동 로그인 — docs/비서컴-setup.md 참고.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TRIG="$REPO_DIR/scripts/trigger.sh"
LA="$HOME/Library/LaunchAgents"
LOGS="$HOME/Library/Logs"
UID_NUM="$(id -u)"

chmod +x "$TRIG" "$REPO_DIR/scripts/install_triggers.sh" "$REPO_DIR/scripts/push_kr_stores.sh"
mkdir -p "$LA" "$LOGS"

make_plist() { # label hour minute script [arg]
  local label="$1" hour="$2" min="$3" script="$4" arg="${5:-}"
  local plist="$LA/$label.plist"
  local argline=""
  [ -n "$arg" ] && argline="    <string>$arg</string>"
  cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$script</string>
$argline
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>$hour</integer>
    <key>Minute</key><integer>$min</integer>
  </dict>
  <key>StandardOutPath</key><string>$LOGS/$label.out.log</string>
  <key>StandardErrorPath</key><string>$LOGS/$label.err.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>$HOME/bin:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
</dict>
</plist>
EOF
  # 모던 API(bootstrap) 우선, 안되면 레거시(load) 폴백
  launchctl bootout "gui/$UID_NUM" "$plist" 2>/dev/null || true
  launchctl unload "$plist" 2>/dev/null || true
  launchctl bootstrap "gui/$UID_NUM" "$plist" 2>/dev/null || launchctl load "$plist"
  printf '✓ 설치: %-46s %02d:%02d KST → %s %s\n' "$label" "$hour" "$min" "$(basename "$script")" "$arg"
}

# 23:30 원스토어·갤럭시 랭킹 → repo 커밋/푸시(다음 collect 가 병합) | 23:45 수집 | 08:00 발송
make_plist "co.supernewt.gamemarket.krstores" 23 30 "$REPO_DIR/scripts/push_kr_stores.sh"
make_plist "co.supernewt.gamemarket.collect"  23 45 "$TRIG" "daily-collect.yml"
make_plist "co.supernewt.gamemarket.email"     8  0 "$TRIG" "daily-email.yml"

echo ""
echo "설치 완료. 등록 확인:"
echo "  launchctl list | grep gamemarket"
echo "로그:"
echo "  tail -f ~/Library/Logs/game-market-trigger.log"
echo "수동 테스트(발송; 당일 이미 보냈으면 멱등성으로 skip됨):"
echo "  bash $TRIG daily-email.yml"
