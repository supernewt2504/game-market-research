#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
비서컴(M1) 깊은 순위 수집본에서 '자사 2종'만 추려 self_games/<date>.json 생성.

입력: ~/secretary/out/rank/<date>.json   (비서컴 rankcheck OCR, 전체 깊이: 원스토어~300·갤럭시인기~200)
출력: data/self_games/<date>.json         (운영리포트 game-ops 가 GitHub raw 로 읽음)

import_kr_stores.py 와 같은 파싱/정규화를 쓰되 Top100 제한(LIMIT)을 두지 않고
전체 순위에서 자사 게임 위치를 찾는다. 못 찾으면 null(=수집깊이 밖, 순위없음).

이 스크립트는 '비서컴에서' 돈다(입력이 M1 에만 있음). 매일 밤(예: 23:35) 실행 권장.
사용:
  python3 scripts/build_self_games.py              # 최근 N일 백필(기본 21일) 후 커밋·푸시
  python3 scripts/build_self_games.py 2026-11-05   # 특정 날짜만
환경변수: SELF_GAMES_BACKFILL=일수, SELF_GAMES_NO_GIT=1 (커밋/푸시 생략, 테스트용)
"""
import json
import os
import sys
import subprocess
import datetime

from import_kr_stores import norm_title, clean_publisher, pick_chart, STORE_MAP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "data", "self_games")
SRC_DIR = os.path.expanduser(os.environ.get("RANK_SRC_DIR", "~/secretary/out/rank"))
BACKFILL_DAYS = int(os.environ.get("SELF_GAMES_BACKFILL", "21"))

# 자사 게임 매칭 규칙. norm_title(공백·기호 제거, 소문자) 에 title_all 키워드가 모두 들어가면 일치.
# publisher(선택)는 보조 확인. stores 는 game-ops config 의 연동 대상과 일치시킨다.
#   projectA 부족또전쟁 = 원스토어 + 갤럭시
#   projectB 소년가행   = 원스토어만 (game-ops 에서 galaxy 제외)
GAMES = {
    "projectA": {"title_all": ["부족", "전쟁"], "stores": ["onestore", "galaxy"]},
    "projectB": {"title_all": ["소년가행"], "publisher": "dreamplay", "stores": ["onestore"]},
}


def full_rank_list(raw_list):
    """import_kr_stores.to_items 와 동일하나 LIMIT 없음: 유효 rank 정렬 → 제목 중복 제거 → 1..N 재번호."""
    items = [it for it in (raw_list or []) if it.get("title")]
    items.sort(key=lambda it: it["rank"] if isinstance(it.get("rank"), int) and it["rank"] > 0 else 10 ** 9)
    out, seen = [], set()
    for it in items:
        nt = norm_title(it["title"])
        if not nt or nt in seen:
            continue
        seen.add(nt)
        out.append({"rank": len(out) + 1, "nt": nt, "pub": (clean_publisher(it.get("publisher")) or "").lower()})
    return out


def find_rank(ranked, spec):
    for e in ranked:
        if all(k in e["nt"] for k in spec["title_all"]):
            pub = spec.get("publisher")
            if pub and pub not in e["pub"]:
                continue
            return e["rank"]
    return None  # 수집깊이 밖 = 순위없음


def build_for_date(date):
    in_path = os.path.join(SRC_DIR, f"{date}.json")
    if not os.path.exists(in_path):
        return None
    src = json.load(open(in_path, encoding="utf-8"))
    stores = src.get("stores", {})
    lists, depth = {}, {}
    for store, names, key in STORE_MAP:          # key: onestore_popular / onestore_grossing / galaxy_*
        ranked = full_rank_list(pick_chart(stores.get(store, {}), names))
        lists[key] = ranked
        depth[key] = len(ranked)
    games = {}
    for pid, spec in GAMES.items():
        g = {}
        if "onestore" in spec["stores"]:
            g["onestore"] = {"popular": find_rank(lists.get("onestore_popular", []), spec),
                             "grossing": find_rank(lists.get("onestore_grossing", []), spec)}
        if "galaxy" in spec["stores"]:
            g["galaxy"] = {"popular": find_rank(lists.get("galaxy_popular", []), spec),
                           "grossing": find_rank(lists.get("galaxy_grossing", []), spec)}
        games[pid] = g
    return {"date": date, "collected_at": src.get("collected_at", ""),
            "source": "secretary-rankcheck", "depth": depth, "games": games}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    if len(sys.argv) > 1:
        dates = [sys.argv[1]]
    else:
        today = datetime.date.today()
        dates = [(today - datetime.timedelta(days=i)).isoformat() for i in range(BACKFILL_DAYS)]

    written = []
    for date in dates:
        res = build_for_date(date)
        if not res:
            continue
        with open(os.path.join(OUT_DIR, f"{date}.json"), "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        written.append(date)
        a = res["games"].get("projectA", {}).get("onestore", {})
        b = res["games"].get("projectB", {}).get("onestore", {})
        print(f"{date}: 부족또전쟁 원스토어 인기={a.get('popular')} 매출={a.get('grossing')} | "
              f"소년가행 원스토어 인기={b.get('popular')} 매출={b.get('grossing')} "
              f"(수집깊이 원스토어={res['depth'].get('onestore_popular')})")

    if not written:
        print("생성된 self_games 없음 (입력 파일 없음?)", file=sys.stderr)
        return

    if os.environ.get("SELF_GAMES_NO_GIT") == "1":
        print(f"[NO_GIT] {len(written)}일 생성, 커밋/푸시 생략")
        return
    subprocess.run(["git", "-C", ROOT, "add", "data/self_games"], check=True)
    msg = f"self_games: 자사 2종 순위 {written[0]} (+{len(written)}일 백필)"
    r = subprocess.run(["git", "-C", ROOT, "commit", "-m", msg])
    if r.returncode == 0:
        subprocess.run(["git", "-C", ROOT, "push"], check=False)
        print("커밋·푸시 완료:", msg)
    else:
        print("변경 없음(커밋 생략)")


if __name__ == "__main__":
    main()
