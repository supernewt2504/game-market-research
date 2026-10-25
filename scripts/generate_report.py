#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
게임시장조사 - 일일 HTML 리포트 생성기 (v3: 자동화 연동)
입력: data/snapshots/<date>.json, 전일 스냅샷, data/app_meta.json(런칭일·국적),
      data/reasons/<date>.json(상승이유·미디어, research.mjs 산출), report/media.json(데모용)
출력:
  docs/daily/<date>.html  - 웹(GitHub Pages)용: 확인 버튼 = JS 모달(이미지·영상·기사), URL #g-키로 자동 오픈
  docs/index.html         - 최신 리포트로 리다이렉트
  out/email_<date>.html   - 이메일용: 확인 버튼 = Pages 상세로 링크(이미지 미포함, 경량)
규칙: 상승=붉은색(▲), 하락=파란색(▼), NEW, 피쳐드, 확인/미확인
"""
import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
SNAP_DIR = os.path.join(DATA, "snapshots")
REPORT_DIR = os.path.join(ROOT, "report")
DOCS_DIR = os.path.join(ROOT, "docs")
OUT_DIR = os.path.join(ROOT, "out")

CFG = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))
RISE = CFG["research"]["rise_threshold"]
PAGES_URL = (os.environ.get("PAGES_BASE_URL") or CFG["report"].get("pages_base_url") or "").rstrip("/")
TITLE = CFG["report"]["title"]

CHART_META = [
    ("google_popular", "Google Play · 인기(무료)순위", "🟢"),
    ("google_grossing", "Google Play · 매출순위", "🟢"),
    ("apple_popular", "App Store · 인기(무료)순위", "🍎"),
    ("apple_grossing", "App Store · 매출순위", "🍎"),
]
CAT_COLORS = {"신규 오픈": "#188038", "컨텐츠 업데이트": "#1a73e8", "매출 이벤트": "#e8710a",
              "콜라보": "#6c3fd1", "시즌·패스": "#009688"}
CAT_SHORT = {"신규 오픈": "신규", "컨텐츠 업데이트": "업데이트", "매출 이벤트": "이벤트",
             "콜라보": "콜라보", "시즌·패스": "시즌", "기타": "기타"}

# 데모용(API 키 없을 때 '확인' UX 시연). 운영에서는 research.mjs 결과가 우선.
DEMO_REASONS = {
    "도깨비의세계": {"category": "신규 오픈", "short": "카카오게임즈 신작, 과금 부담 완화로 매출 1위",
        "summary": "카카오게임즈 신작. 꾸미기 상품에 성장 능력치를 넣지 않는 과금 부담 완화 BM과 2.5D 그래픽, "
                   "출시 직후 피드백 신속 반영으로 구글 매출 1위.",
        "articles": [{"title": "매출 1위 '도깨비의세계' 흥행 비결은 과금 부담 완화·피드백 반영", "url": "https://inews24.com/view/2015474"}]},
    "운빨존많겜": {"category": "컨텐츠 업데이트", "short": "1주년 업데이트·실질 보상 강화로 상위 유지",
        "summary": "111퍼센트의 운 기반 캐주얼 디펜스. 무과금 친화 BM·2인 협동으로 상위 매출 유지, 1주년 업데이트로 보상 강화.",
        "articles": [{"title": "'운빨존많겜' 슈퍼패스트, 상반기 매출 1000억 돌파", "url": "https://news.mtn.co.kr/news-detail/2026080617340919777"}]},
}
FEATURED_DEMO = {"로블록스", "Whiteout Survival", "블록 블라스트"}


def kst_today():
    return (datetime.now(timezone.utc) + timedelta(hours=9)).date()


def load(path, default):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else default


def make_demo_prev(today_snap):
    rnd = random.Random(42)
    prev = {"charts": {}}
    for key, items in today_snap["charts"].items():
        pl = []
        drop = set(rnd.sample([it["id"] for it in items[20:90]], k=6))
        for it in items:
            if it["id"] in drop:
                continue
            pl.append({"id": it["id"], "rank": max(1, it["rank"] + rnd.choice([0, 0, 1, -1, 2, -2, 3, -3, 5, -5, 8, -8, 12]))})
        for it in pl:
            pass
        pl.sort(key=lambda x: x["rank"])
        for i, it in enumerate(pl):
            it["rank"] = i + 1
        prev["charts"][key] = pl
    return prev


def diff_chart(today_items, prev_items):
    pm = {it["id"]: it["rank"] for it in prev_items}
    rows = []
    for it in today_items:
        pr = pm.get(it["id"])
        if pr is None:
            change = {"type": "new"}
        else:
            d = pr - it["rank"]
            change = {"type": "up", "delta": d} if d > 0 else ({"type": "down", "delta": -d} if d < 0 else {"type": "same"})
        rows.append({**it, "change": change})
    return rows


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def flag(country):
    if not country or len(country) != 2 or not country.isalpha():
        return ""
    b = 0x1F1E6
    return chr(b + ord(country[0].upper()) - 65) + chr(b + ord(country[1].upper()) - 65)


def change_cell(ch):
    t = ch["type"]
    if t == "up":
        return f'<span style="color:#d93025;font-weight:700;">▲ {ch["delta"]}</span>'
    if t == "down":
        return f'<span style="color:#1a73e8;font-weight:700;">▼ {ch["delta"]}</span>'
    if t == "new":
        return '<span style="background:#d93025;color:#fff;font-size:11px;font-weight:700;padding:2px 6px;border-radius:4px;">NEW</span>'
    return '<span style="color:#9aa0a6;">—</span>'


def badges(name):
    if any(f in name for f in FEATURED_DEMO):
        return '<span style="background:#6c3fd1;color:#fff;font-size:10px;font-weight:700;padding:1px 6px;border-radius:4px;margin-left:6px;">피쳐드</span>'
    return ""


def cat_tag(category):
    c = CAT_COLORS.get(category, "#5f6368")
    return (f'<span style="display:inline-block;vertical-align:middle;background:{c};color:#fff;font-size:10px;font-weight:700;'
            f'padding:1px 7px;border-radius:10px;margin-right:5px;white-space:nowrap;">{esc(category)}</span>')


def is_mover(row):
    ch = row["change"]
    return ch["type"] == "new" or (ch["type"] == "up" and ch.get("delta", 0) >= RISE)


def reason_for_row(row, reasons_by_id, demo_keys):
    """(key, reason) 반환. 우선 research 결과(id), 없으면 데모(이름)."""
    r = reasons_by_id.get(row["id"])
    if r:
        return row["id"], r
    for name, key in demo_keys.items():
        if name in row["name"]:
            return key, None  # 데모는 DETAILS에서 key로 조회
    return None, None


def bigo_cell(row, reasons_by_id, demo_keys, demo_details, date, mode):
    if not is_mover(row) and row["id"] not in reasons_by_id and not any(n in row["name"] for n in demo_keys):
        return ""
    key, r = reason_for_row(row, reasons_by_id, demo_keys)
    # 데모 처리
    if r is None and key is not None:
        d = demo_details[key]
        verified, category, short = True, d["category"], d["short"]
    elif r is not None:
        verified, category, short = bool(r.get("verified")), r.get("category") or "확인 필요", r.get("short") or ""
    else:
        verified, category, short = False, "확인 필요", ""

    pieces = []
    if category and category != "확인 필요":
        pieces.append(cat_tag(category))
    elif not verified:
        pieces.append('<span style="display:inline-block;vertical-align:middle;background:#f1f3f4;color:#80868b;font-size:10px;font-weight:700;padding:1px 7px;border-radius:10px;margin-right:5px;white-space:nowrap;">확인 필요</span>')
    if short:
        pieces.append(f'<span style="vertical-align:middle;color:#3c4043;">{esc(short)}</span>')
    elif not verified:
        pieces.append('<span style="vertical-align:middle;color:#9aa0a6;">원인 조사 중</span>')

    if verified and key is not None:
        if mode == "web":
            btn = (f'<button onclick="openDetail(\'{esc(key)}\')" style="display:inline-block;vertical-align:middle;margin-left:5px;background:#e6f4ea;color:#188038;'
                   f'border:1px solid #a8dab5;border-radius:12px;font-size:11px;font-weight:700;padding:2px 9px;cursor:pointer;white-space:nowrap;">확인 ▸</button>')
        else:  # email
            if PAGES_URL:
                btn = (f'<a href="{PAGES_URL}/daily/{date}.html#g-{esc(key)}" style="display:inline-block;vertical-align:middle;margin-left:5px;background:#e6f4ea;color:#188038;'
                       f'border:1px solid #a8dab5;border-radius:12px;font-size:11px;font-weight:700;padding:2px 9px;text-decoration:none;white-space:nowrap;">확인 ▸</a>')
            else:
                btn = '<span style="vertical-align:middle;margin-left:5px;color:#188038;font-weight:700;">확인</span>'
        pieces.append(btn)
    elif not verified:
        pieces.append('<span style="display:inline-block;vertical-align:middle;margin-left:5px;background:#fce8e6;color:#c5221f;border:1px solid #f6aea9;border-radius:12px;font-size:11px;font-weight:700;padding:2px 9px;white-space:nowrap;">미확인</span>')

    return '<div style="line-height:1.9;">' + "".join(pieces) + '</div>'


def render_table(title, icon, rows, meta, reasons_by_id, demo_keys, demo_details, date, mode):
    head = ('<tr style="background:#f1f3f4;color:#5f6368;font-size:12px;text-align:left;">'
            '<th style="padding:8px 10px;width:44px;">순위</th>'
            '<th style="padding:8px 10px;width:60px;">변동</th>'
            '<th style="padding:8px 10px;">게임명</th>'
            '<th style="padding:8px 10px;width:160px;">개발사</th>'
            '<th style="padding:8px 10px;width:92px;">런칭일</th>'
            '<th style="padding:8px 10px;">비고 / 상승 이유</th></tr>')
    trs = []
    for row in rows:
        bg = "#fff" if row["rank"] % 2 else "#fafafa"
        link = f'<a href="{esc(row["url"])}" target="_blank" style="color:#202124;text-decoration:none;word-break:keep-all;">{esc(row["name"])}</a>'
        m = meta.get(row["id"], {})
        fl = flag(m.get("country"))
        fl_sp = (fl + " ") if fl else ""
        released = m.get("released") or "<span style='color:#c0c3c7;'>—</span>"
        trs.append(
            f'<tr style="background:{bg};border-bottom:1px solid #f1f3f4;font-size:13px;">'
            f'<td style="padding:7px 10px;color:#80868b;font-weight:700;">{row["rank"]}</td>'
            f'<td style="padding:7px 10px;">{change_cell(row["change"])}</td>'
            f'<td style="padding:7px 10px;color:#202124;">{link}{badges(row["name"])}</td>'
            f'<td style="padding:7px 10px;color:#5f6368;">{fl_sp}{esc(row["developer"])}</td>'
            f'<td style="padding:7px 10px;color:#5f6368;font-size:12px;white-space:nowrap;">{released}</td>'
            f'<td style="padding:7px 10px;font-size:12px;">{bigo_cell(row, reasons_by_id, demo_keys, demo_details, date, mode)}</td>'
            f'</tr>')
    return (f'<h2 style="font-size:17px;color:#202124;margin:30px 0 10px;">{icon} {esc(title)}</h2>'
            f'<div style="overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid #e8eaed;border-radius:8px;">'
            f'<table style="width:100%;min-width:680px;border-collapse:collapse;">{head}{"".join(trs)}</table></div>')


def badge_pill(text, bg, fg, border=None, href=None):
    style = (f'display:inline-block;vertical-align:middle;background:{bg};color:{fg};font-size:10px;'
             f'font-weight:700;padding:1px 7px;border-radius:10px;margin-left:4px;white-space:nowrap;'
             + (f'border:1px solid {border};' if border else ''))
    if href:
        return f'<a href="{href}" style="{style}text-decoration:none;">{esc(text)}</a>'
    return f'<span style="{style}">{esc(text)}</span>'


def bigo_parts(row, reasons_by_id, demo_keys, demo_details, date):
    """모바일용: (게임명 옆 배지들, 하단 사유텍스트) 반환."""
    if not is_mover(row) and row["id"] not in reasons_by_id and not any(n in row["name"] for n in demo_keys):
        return "", ""
    key, r = reason_for_row(row, reasons_by_id, demo_keys)
    if r is None and key is not None:
        d = demo_details[key]
        verified, category, short = True, d["category"], d["short"]
    elif r is not None:
        verified, category, short = bool(r.get("verified")), r.get("category") or "확인 필요", r.get("short") or ""
    else:
        verified, category, short = False, "확인 필요", ""
    b = ""
    if category and category != "확인 필요":
        b += badge_pill(CAT_SHORT.get(category, category), CAT_COLORS.get(category, "#5f6368"), "#fff")
    if verified and key is not None:
        href = f"{PAGES_URL}/daily/{date}.html#g-{esc(key)}" if PAGES_URL else None
        b += badge_pill("확인", "#e6f4ea", "#188038", "#a8dab5", href=href)
    elif not verified:
        b += badge_pill("미확인", "#fce8e6", "#c5221f", "#f6aea9")
    reason = esc(short) if short else ("원인 조사 중" if not verified else "")
    return b, reason


def render_chart_email(title, icon, rows, meta, reasons_by_id, demo_keys, demo_details, date):
    """이메일용 모바일 친화 레이아웃: 2열(순위/변동 | 게임·개발사·런칭일·비고 스택)."""
    trs = []
    for row in rows:
        bg = "#fff" if row["rank"] % 2 else "#fafafa"
        m = meta.get(row["id"], {})
        fl = flag(m.get("country"))
        released = m.get("released") or "—"
        link = f'<a href="{esc(row["url"])}" target="_blank" style="color:#202124;text-decoration:none;word-break:keep-all;">{esc(row["name"])}</a>'
        name_badges, reason_text = bigo_parts(row, reasons_by_id, demo_keys, demo_details, date)
        reason_block = (f'<div style="font-size:11px;color:#5f6368;margin-top:4px;word-break:keep-all;line-height:1.5;">{reason_text}</div>'
                        if reason_text else "")
        devline = f'{(fl + " ") if fl else ""}{esc(row["developer"])} <span style="color:#9aa0a6;">· {released}</span>'
        trs.append(
            f'<tr style="background:{bg};border-bottom:1px solid #eef0f1;">'
            f'<td valign="top" style="padding:10px 6px 10px 12px;width:46px;white-space:nowrap;">'
            f'<span style="color:#80868b;font-weight:700;font-size:14px;">{row["rank"]}</span><br>'
            f'<span style="font-size:12px;">{change_cell(row["change"])}</span></td>'
            f'<td valign="top" style="padding:10px 12px 10px 0;">'
            f'<div style="font-size:14px;color:#202124;font-weight:600;word-break:keep-all;line-height:1.5;">{link}{badges(row["name"])}{name_badges}</div>'
            f'<div style="font-size:12px;color:#5f6368;margin-top:2px;word-break:keep-all;">{devline}</div>'
            f'{reason_block}</td></tr>'
        )
    return (f'<h2 style="font-size:17px;color:#202124;margin:28px 0 8px;">{icon} {esc(title)}</h2>'
            f'<table role="presentation" style="width:100%;border-collapse:collapse;border:1px solid #e8eaed;border-radius:8px;overflow:hidden;">{"".join(trs)}</table>')


def build_details(reasons_by_id, demo_details):
    """verified 상세(모달용). id 기준 + 데모 key 기준 병합."""
    details = {}
    for gid, r in reasons_by_id.items():
        if not r.get("verified"):
            continue
        details[gid] = {"title": r.get("title") or gid, "category": r.get("category", ""),
                        "summary": r.get("summary", ""), "articles": r.get("articles", []),
                        "icon": r.get("icon"), "screenshots": r.get("screenshots", []),
                        "video": r.get("video"), "videoImage": r.get("videoImage"), "storeUrl": r.get("storeUrl")}
    details.update(demo_details)
    return details


def modal_block(details):
    dj = json.dumps(details, ensure_ascii=False).replace("</", "<\\/")
    return """
<script>
const DETAILS = %s;
function imgTag(u){return u?('<img loading="lazy" src="'+u+'" style="height:230px;border-radius:8px;margin:0 8px 0 0;flex:0 0 auto;">'):'';}
function openDetail(key){
  const d = DETAILS[key]; if(!d) return;
  const arts=(d.articles||[]).map(a=>'<li style="margin:4px 0;"><a href="'+a.url+'" target="_blank" style="color:#1a73e8;text-decoration:none;">'+a.title+'</a></li>').join('');
  const shots=(d.screenshots||[]).map(imgTag).join('');
  let video='';
  if(d.video){const poster=d.videoImage?'<img loading="lazy" src="'+d.videoImage+'" style="width:100%%;max-width:420px;border-radius:8px;display:block;">':'';
    video='<div style="margin-top:14px;"><div style="font-weight:700;color:#202124;margin-bottom:6px;">🎬 프로모 영상</div><a href="'+d.video+'" target="_blank" style="position:relative;display:inline-block;text-decoration:none;">'+poster+'<span style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:44px;color:#fff;text-shadow:0 2px 8px rgba(0,0,0,.6);">▶</span></a></div>';}
  document.getElementById('modalBody').innerHTML=
    '<div style="display:flex;align-items:center;gap:12px;padding:18px 20px;border-bottom:1px solid #eee;">'
    +(d.icon?'<img src="'+d.icon+'" style="width:52px;height:52px;border-radius:12px;">':'')
    +'<div><div style="font-size:18px;font-weight:800;color:#202124;">'+d.title+'</div>'
    +(d.category?'<div style="margin-top:3px;"><span style="background:#188038;color:#fff;font-size:11px;font-weight:700;padding:2px 8px;border-radius:10px;">'+d.category+'</span></div>':'')+'</div></div>'
    +'<div style="padding:18px 20px;"><div style="color:#3c4043;line-height:1.7;">'+d.summary+'</div>'
    +(shots?'<div style="display:flex;overflow-x:auto;margin-top:16px;padding-bottom:6px;">'+shots+'</div>':'')+video
    +(arts?'<div style="margin-top:16px;font-weight:700;color:#202124;">📰 관련 기사</div><ul style="margin:6px 0 0;padding-left:18px;font-size:13px;">'+arts+'</ul>':'')
    +(d.storeUrl?'<div style="margin-top:14px;"><a href="'+d.storeUrl+'" target="_blank" style="color:#5f6368;font-size:12px;">스토어 페이지 →</a></div>':'')+'</div>';
  document.getElementById('overlay').style.display='block'; document.body.style.overflow='hidden';
}
function closeDetail(e){if(e&&e.target&&e.target.id!=='overlay'&&e.type==='click')return;document.getElementById('overlay').style.display='none';document.body.style.overflow='';}
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeDetail();});
window.addEventListener('load',()=>{const h=location.hash;if(h&&h.indexOf('#g-')===0){openDetail(decodeURIComponent(h.slice(3)));}});
</script>
<div id="overlay" onclick="closeDetail(event)" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:999;padding:24px 16px;overflow:auto;">
  <div style="max-width:720px;margin:0 auto;background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 12px 40px rgba(0,0,0,.3);">
    <div style="text-align:right;padding:6px 10px 0;"><button onclick="closeDetail()" style="border:none;background:none;font-size:22px;color:#80868b;cursor:pointer;">×</button></div>
    <div id="modalBody"></div></div></div>
""" % dj


def page_html(date, ct_kst, demo, diffed, meta, reasons_by_id, demo_keys, demo_details, mode, chart_keys=None, platform=None):
    legend = ('<div style="font-size:12px;color:#5f6368;margin:8px 0;">'
              '<span style="color:#d93025;font-weight:700;">▲ 상승</span> &nbsp; '
              '<span style="color:#1a73e8;font-weight:700;">▼ 하락</span> &nbsp; '
              '<span style="color:#9aa0a6;">— 변동없음</span> &nbsp; '
              '<span style="background:#d93025;color:#fff;font-size:10px;font-weight:700;padding:1px 6px;border-radius:4px;">NEW</span> 신규 &nbsp; '
              '<span style="background:#6c3fd1;color:#fff;font-size:10px;font-weight:700;padding:1px 6px;border-radius:4px;">피쳐드</span> 추천 &nbsp; '
              '<span style="color:#188038;font-weight:700;">확인 ▸</span> 근거 상세 &nbsp; '
              '<span style="color:#c5221f;font-weight:700;">미확인</span> 조사중</div>')
    demo_banner = ('<div style="background:#fef7e0;border:1px solid #feefc3;color:#7a5900;padding:9px 13px;border-radius:8px;margin:14px 0;font-size:12px;">'
                   '⚠️ 샘플: 전일 데이터가 없어 변동(▲▼·NEW)은 시연용입니다. 내일부터 실제 전일 비교가 적용됩니다.</div>' if demo else "")
    keys = [(k, t, i) for k, t, i in CHART_META if chart_keys is None or k in chart_keys]
    if mode == "email":
        tables = "".join(render_chart_email(t, i, diffed[k], meta, reasons_by_id, demo_keys, demo_details, date) for k, t, i in keys)
    else:
        tables = "".join(render_table(t, i, diffed[k], meta, reasons_by_id, demo_keys, demo_details, date, mode) for k, t, i in keys)
    modal = modal_block(build_details(reasons_by_id, demo_details)) if mode == "web" else ""
    foot = ('데이터: Apple iTunes RSS · Google Play. 상승이유는 매출 NEW·상승폭 큰 게임을 웹검색으로 조사하고, '
            '기사가 없으면 스토어 업데이트 내역을 확인해 작성합니다. 이미지/영상은 스토어 CDN을 폭 제한으로 참조해 용량을 최소화합니다.')
    maxw = 640 if mode == "email" else 940  # 이메일은 고정 폭 중앙정렬(PC·모바일 모두 자연스럽게)
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(TITLE)} — {date}</title></head>
<body style="margin:0;background:#f5f6f7;font-family:-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;">
<div style="max-width:{maxw}px;margin:0 auto;padding:24px 16px 48px;">
  <div style="background:#202124;color:#fff;border-radius:12px;padding:20px 22px;">
    <div style="font-size:21px;font-weight:800;">📊 {esc(TITLE)}{(' — ' + esc(platform)) if platform else ''}</div>
    <div style="font-size:13px;color:#c7c9cc;margin-top:4px;">대한민국 · {esc(platform) if platform else 'Google Play &amp; App Store'} · 게임 Top 100</div>
    <div style="font-size:12px;color:#9aa0a6;margin-top:7px;">기준일 {date} &nbsp;|&nbsp; 집계 {esc(ct_kst)} (KST)</div>
  </div>
  {demo_banner}{legend}{tables}
  <div style="margin-top:34px;color:#9aa0a6;font-size:12px;line-height:1.7;border-top:1px solid #e8eaed;padding-top:14px;">{foot}</div>
</div>{modal}
</body></html>"""


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else str(kst_today())
    today_snap = load(os.path.join(SNAP_DIR, f"{date}.json"), None)
    if not today_snap:
        print("스냅샷 없음:", date, file=sys.stderr); sys.exit(1)
    prev_date = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    prev_snap = load(os.path.join(SNAP_DIR, f"{prev_date}.json"), None)
    demo = prev_snap is None
    if demo:
        prev_snap = make_demo_prev(today_snap)

    diffed = {k: diff_chart(today_snap["charts"][k], prev_snap["charts"][k]) for k, _, _ in CHART_META}
    meta = load(os.path.join(DATA, "app_meta.json"), {})
    reasons_by_id = load(os.path.join(DATA, "reasons", f"{date}.json"), {})
    demo_media = load(os.path.join(REPORT_DIR, "media.json"), {})

    # 데모 상세 구성(이름->key), research 결과가 비었을 때 '확인' UX 시연용
    demo_keys, demo_details = {}, {}
    any_verified = any(r.get("verified") for r in reasons_by_id.values())
    if not any_verified:
        for i, (name, dr) in enumerate(DEMO_REASONS.items()):
            key = f"demo{i}"
            demo_keys[name] = key
            md = demo_media.get(name, {})
            demo_details[key] = {"title": name, "category": dr["category"], "short": dr["short"], "summary": dr["summary"],
                                 "articles": dr["articles"], "icon": md.get("icon"), "screenshots": md.get("screenshots", []),
                                 "video": md.get("video"), "videoImage": md.get("videoImage"), "storeUrl": md.get("storeUrl")}

    collected = today_snap.get("collectedAt", "")
    try:
        ct = datetime.fromisoformat(collected.replace("Z", "+00:00"))
        ct_kst = (ct + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        ct_kst = collected

    os.makedirs(os.path.join(DOCS_DIR, "daily"), exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    web = page_html(date, ct_kst, demo, diffed, meta, reasons_by_id, demo_keys, demo_details, "web")
    with open(os.path.join(DOCS_DIR, "daily", f"{date}.html"), "w", encoding="utf-8") as f:
        f.write(web)
    # index.html -> 최신으로 리다이렉트
    with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=daily/{date}.html">'
                f'<a href="daily/{date}.html">{esc(TITLE)} {date}</a>')

    # 이메일: 구글/애플 분리 발송
    platforms = {
        "google": (["google_popular", "google_grossing"], "Google Play"),
        "apple": (["apple_popular", "apple_grossing"], "App Store"),
    }
    for pkey, (keys, label) in platforms.items():
        em = page_html(date, ct_kst, demo, diffed, meta, reasons_by_id, demo_keys, demo_details, "email",
                       chart_keys=keys, platform=label)
        with open(os.path.join(OUT_DIR, f"email_{pkey}_{date}.html"), "w", encoding="utf-8") as f:
            f.write(em)

    # 미리보기 호환: 기존 샘플 경로도 갱신(통합 웹 버전)
    with open(os.path.join(REPORT_DIR, "sample_report.html"), "w", encoding="utf-8") as f:
        f.write(web)

    print(f"생성: docs/daily/{date}.html, out/email_google_{date}.html, out/email_apple_{date}.html (demo={demo}, verified={any_verified})")


if __name__ == "__main__":
    main()
