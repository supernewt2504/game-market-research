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
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "data", "kr_stores")
ICON_CACHE = os.path.join(OUT_DIR, "_icons.json")  # norm_title → 아이콘 URL (영구 캐시)

# 원스토어 아이콘 해석: 비서컴(한국 IP)에서만 가능(원스토어가 비한국 IP 지역차단).
# GitHub 러너는 여기서 행에 심은 icon 을 그대로 사용한다(네트워크 불필요).
UA_DESKTOP = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36")
_EL_RE = re.compile(
    r'\\"prodId\\":\\"(\d+)\\"[\s\S]{0,600}?\\"title\\":\\"([^"\\]+)\\",'
    r'\\"creator\\":\\"([^"\\]*)\\"[\s\S]{0,400}?\\"mainImageUrl\\":\\"(https:[^"\\]+?)\\"')


ALIAS_PATH = os.path.join(ROOT, "data", "kr_title_alias.json")
_ALIAS = None


def _load_aliases():
    """OCR 제목 오인식 교정 규칙 로드(data/kr_title_alias.json)."""
    global _ALIAS
    if _ALIAS is not None:
        return _ALIAS
    _ALIAS = []
    try:
        raw = json.load(open(ALIAS_PATH, encoding="utf-8"))
        for a in raw.get("aliases", []):
            if not a.get("title"):
                continue
            _ALIAS.append({
                "pub": (a.get("pub") or "").lower(),
                "title_re": re.compile(a["title_re"], re.I) if a.get("title_re") else None,
                "title": a["title"],
                "icon": a.get("icon"),
                "released": a.get("released"),
            })
    except Exception:
        _ALIAS = []
    return _ALIAS


def correct_title(title, publisher):
    """OCR 깨진 제목을 alias 규칙으로 canonical 제목에 매핑(publisher+title 동시 일치 시)."""
    t = (title or "")
    pub = (publisher or "").lower()
    for a in _load_aliases():
        if a["pub"] and a["pub"] not in pub:
            continue
        if a["title_re"] and not a["title_re"].search(t.lower()):
            continue
        return a["title"]
    return title


def onestore_search(name):
    """원스토어 공개 검색(SSR) → [(title, icon_url), ...] 상위 몇 건."""
    term = re.sub(r"(?i)\s*for\s*onestore", "", name or "")
    term = re.sub(r"\s*[•…]+.*$", "", term).strip()
    if not term:
        return []
    url = "https://m.onestore.co.kr/v2/ko-kr/search?keyword=" + urllib.parse.quote(term)
    req = urllib.request.Request(url, headers={"User-Agent": UA_DESKTOP})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode("utf-8", "replace")
    except Exception:
        return []
    out = []
    for m in _EL_RE.finditer(html):  # (prodId, title, iconUrl)
        out.append((m.group(1), m.group(2), urllib.parse.unquote(m.group(4))))
        if len(out) >= 8:
            break
    return out


_DATE_RE = re.compile(r'\\"releaseDate\\":\\"(\d{8})')


def onestore_release(pid):
    """원스토어 상세 페이지의 releaseDate(해당 스토어 최초 출시일) → YYYY.MM.DD."""
    url = f"https://m.onestore.co.kr/v2/ko-kr/app/{pid}"
    req = urllib.request.Request(url, headers={"User-Agent": UA_DESKTOP})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode("utf-8", "replace")
    except Exception:
        return None
    ds = [m.group(1) for m in _DATE_RE.finditer(html)]
    if not ds:
        return None
    d = min(ds)  # 여러 버전 중 가장 이른 날짜 = 최초 출시
    return f"{d[0:4]}.{d[4:6]}.{d[6:8]}"


def resolve_meta(name):
    """게임명 → 원스토어 {icon, released}. 제목 정규화 일치/접두 겹침으로 매칭."""
    q = norm_title(name)
    if not q:
        return None
    items = onestore_search(name) or onestore_search(name)  # 1회 재시도
    if not items:
        return None
    hit = None
    for pid, t, ic in items:  # 완전일치 우선
        if norm_title(t) == q:
            hit = (pid, ic); break
    if not hit:
        for pid, t, ic in items:  # 접두 6자 겹침
            nt = norm_title(t)
            if nt and (q[:6] in nt or nt[:6] in q):
                hit = (pid, ic); break
    if not hit:
        return None
    pid, ic = hit
    return {"icon": ic, "released": onestore_release(pid)}


def _norm_cache(v):
    """구(아이콘 문자열) 캐시 호환 → dict."""
    if isinstance(v, str):
        return {"icon": v}
    return v if isinstance(v, dict) else {}


def add_icons(charts):
    """모든 국내스토어 행에 아이콘+출시일을 심는다(영구 캐시로 신규/미보완만 조회)."""
    try:
        cache = json.load(open(ICON_CACHE, encoding="utf-8")) if os.path.exists(ICON_CACHE) else {}
    except Exception:
        cache = {}
    cache = {k: _norm_cache(v) for k, v in cache.items()}
    # alias canonical 게임의 아이콘·출시일을 캐시에 선반영(검색 실패 대비)
    for a in _load_aliases():
        k = norm_title(a["title"])
        if not k or not (a.get("icon") or a.get("released")):
            continue
        c = cache.setdefault(k, {})
        if a.get("icon"):
            c["icon"] = c.get("icon") or a["icon"]
        if a.get("released"):
            c["released"] = c.get("released") or a["released"]
    # 캐시에 없거나 출시일이 아직 없는 고유 게임명만 조회(출시일 백필 포함)
    todo = {}
    for rows in charts.values():
        for it in rows:
            k = norm_title(it["name"])
            if not k or k in todo:
                continue
            c = cache.get(k)
            if c is None or not c.get("released"):
                todo[k] = it["name"]
    if todo:
        keys = list(todo)
        with ThreadPoolExecutor(max_workers=4) as ex:
            res = list(ex.map(lambda k: resolve_meta(todo[k]), keys))
        for k, r in zip(keys, res):
            if r and (r.get("icon") or r.get("released")):
                prev = cache.get(k, {})
                cache[k] = {"icon": r.get("icon") or prev.get("icon"),
                            "released": r.get("released") or prev.get("released")}
        try:
            with open(ICON_CACHE, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=0, sort_keys=True)
        except Exception:
            pass
    nic = nrel = 0
    for rows in charts.values():
        for it in rows:
            c = cache.get(norm_title(it["name"]))
            if not c:
                continue
            if c.get("icon"):
                it["icon"] = c["icon"]; nic += 1
            if c.get("released"):
                it["released"] = c["released"]; nrel += 1
    print(f"원스토어 보강: 아이콘 {nic}·출시일 {nrel} 심음(신규조회 {len(todo)})", file=sys.stderr)

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
        ctitle = correct_title(it["title"], it.get("publisher"))  # OCR 오인식 교정
        nt = norm_title(ctitle)
        gid = f"{ID_PREFIX[prefix]}:{nt}"
        if not nt or gid in seen:
            continue
        seen.add(gid)
        out.append({
            "rank": len(out) + 1,
            "name": ctitle.strip(),
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
    add_icons(charts)  # 원스토어 아이콘 심기(비서컴 한국 IP)
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
