#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
비서컴(M1) 원스토어·갤럭시 랭킹(OCR 수집본)을 repo 차트 포맷으로 변환.
입력: ~/secretary/out/rank/<date>.json  (비서컴 rankcheck 산출, OCR 기반)
출력: data/kr_stores/<date>.json        (collect.mjs 가 스냅샷에 병합)

이 스크립트는 '비서컴에서' 돈다(입력 파일이 M1에만 있음). GitHub 러너는 산출된
data/kr_stores/<date>.json 만 읽는다. OCR 기반이라 앱ID·URL·아이콘은 없음(순위·게임명·개발사만).

사용: python3 scripts/import_kr_stores.py <YYYY-MM-DD> [입력json경로]
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "data", "kr_stores")

# M1 rank json 의 (스토어, 차트) → repo 차트키. 갤럭시 '최고 매출'(공백) 표기 변형 모두 수용.
STORE_MAP = [
    ("원스토어", ["최고매출", "최고 매출"], "onestore_grossing"),
    ("원스토어", ["인기"], "onestore_popular"),
    ("갤럭시 스토어", ["최고 매출", "최고매출"], "galaxy_grossing"),
    ("갤럭시 스토어", ["인기"], "galaxy_popular"),
]
ID_PREFIX = {"onestore": "one", "galaxy": "gal"}
LIMIT = 100


def norm_title(t):
    """일자 간 동일 게임 매칭용 정규화(공백·기호·OCR 꼬리 제거)."""
    t = (t or "").lower()
    t = re.sub(r"for\s*onestore|for\s*samsung", "", t)
    t = t.replace("•••", "").replace("...", "").replace("…", "")
    t = re.sub(r"[^0-9a-z가-힣]", "", t)
    return t


def clean_publisher(p):
    """갤럭시 등 저작권 문구(Copyright ©... All Rights Reserved) 정리 → 회사명만."""
    p = (p or "").strip()
    if not p:
        return ""
    p = re.sub(r"(?i)copyright", "", p)
    p = p.lstrip("©@®™ ").strip()
    i = p.find("©")               # 여러 저작권 병기 시 첫 © 앞까지
    if i > 0:
        p = p[:i]
    p = re.sub(r"(?i)[\.,]?\s*all rights reserved\.?.*$", "", p)
    p = p.strip(" .,·-")
    return p


def pick_chart(charts, names):
    for n in names:
        if n in charts:
            return charts[n]
    return None


def to_items(raw_list, prefix):
    """OCR rank(0/중복 가능) 보정: 유효 rank로 정렬 후 위치로 재번호. id 중복 제거, Top100."""
    items = [it for it in (raw_list or []) if it.get("title")]
    items.sort(key=lambda it: it["rank"] if isinstance(it.get("rank"), int) and it["rank"] > 0 else 10**9)
    out, seen = [], set()
    for it in items:
        gid = f"{ID_PREFIX[prefix]}:{norm_title(it['title'])}"
        if not norm_title(it["title"]) or gid in seen:
            continue
        seen.add(gid)
        out.append({
            "rank": len(out) + 1,
            "name": it["title"].strip(),
            "id": gid,
            "developer": clean_publisher(it.get("publisher")),
            "url": "",
        })
        if len(out) >= LIMIT:
            break
    return out


def main():
    if len(sys.argv) < 2:
        print("사용: import_kr_stores.py <YYYY-MM-DD> [입력json경로]", file=sys.stderr)
        sys.exit(2)
    date = sys.argv[1]
    in_path = sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser(f"~/secretary/out/rank/{date}.json")
    if not os.path.exists(in_path):
        print(f"입력 없음: {in_path} → 생성 생략(수집 실패일로 간주)", file=sys.stderr)
        sys.exit(1)

    src = json.load(open(in_path, encoding="utf-8"))
    stores = src.get("stores", {})
    charts = {}
    for store, names, key in STORE_MAP:
        raw = pick_chart(stores.get(store, {}), names)
        prefix = "onestore" if key.startswith("onestore") else "galaxy"
        items = to_items(raw, prefix)
        if items:
            charts[key] = items

    if not charts:
        print("변환 결과 비어 있음 → 생성 생략", file=sys.stderr)
        sys.exit(1)

    os.makedirs(OUT_DIR, exist_ok=True)
    out = {
        "date": date,
        "collected_at": src.get("collected_at", ""),
        "source": "secretary-ocr",
        "charts": charts,
    }
    with open(os.path.join(OUT_DIR, f"{date}.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("생성:", os.path.join("data", "kr_stores", f"{date}.json"),
          "|", ", ".join(f"{k}={len(v)}" for k, v in charts.items()))


if __name__ == "__main__":
    main()
