#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
이메일 발송 (Google Workspace SMTP). out/email_<date>.html 을 HTML 메일로 전송.
환경변수: SMTP_USER, SMTP_PASS(앱 비밀번호), MAIL_TO(쉼표구분, 선택)
설정: config.json 의 email 섹션
사용: python3 scripts/send_email.py 2026-10-25
"""
import json
import os
import smtplib
import ssl
import sys
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr, formatdate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))["email"]

# 발신 정보는 환경변수로 교체 가능(없으면 config 폴백).
# 운영리포트 계정과 분리하려면 전용 발신 계정/ESP의 값을 Secrets/Variables로 주입.
MAIL_FROM = os.environ.get("MAIL_FROM") or CFG["from"]
SMTP_HOST = os.environ.get("SMTP_HOST") or CFG["smtp_host"]
SMTP_PORT = int(os.environ.get("SMTP_PORT") or CFG["smtp_port"])


def kst_today():
    return (datetime.now(timezone.utc) + timedelta(hours=9)).date()


PLATFORMS = [("google", "Google Play"), ("apple", "App Store"), ("kr_stores", "국내 스토어")]

# 멱등성 마커: "<날짜>:<보낸 플랫폼 목록>" 한 줄(예: 2026-11-05:apple,google,kr_stores).
# 플랫폼 단위로 기록하므로, 같은 날짜라도 뒤늦게 생긴 차트(예: 원스토어·갤럭시)만 골라
# 재발송할 수 있다(이미 보낸 구글·애플은 중복 안 됨). 구 형식(날짜만)도 읽는다.
MARKER = os.path.join(ROOT, "data", "last_emailed.txt")


def read_marker():
    """마커 → (날짜, 보낸 플랫폼 집합). 없거나 구형식이면 집합은 비거나 부분."""
    try:
        with open(MARKER, encoding="utf-8") as f:
            line = f.read().strip()
    except FileNotFoundError:
        return (None, set())
    if not line:
        return (None, set())
    if ":" in line:
        d, plats = line.split(":", 1)
        return (d.strip(), {p for p in (x.strip() for x in plats.split(",")) if p})
    return (line, set())  # 구 형식(날짜만) — 어떤 플랫폼을 보냈는지는 미기록


def write_marker(date, plats):
    os.makedirs(os.path.dirname(MARKER), exist_ok=True)
    with open(MARKER, "w", encoding="utf-8") as f:
        f.write(f"{date}:{','.join(sorted(plats))}\n")


def latest_date():
    import glob
    dates = set()
    for pkey, _ in PLATFORMS:
        for p in glob.glob(os.path.join(ROOT, "out", f"email_{pkey}_*.html")):
            dates.add(os.path.basename(p).rsplit("_", 1)[1][:-5])
    return max(dates) if dates else None  # ISO 날짜 문자열 정렬 = 시간순


def present_platforms(date):
    """해당 날짜에 실제 메일 파일이 존재하는 플랫폼 키 목록(PLATFORMS 순서 유지)."""
    return [pkey for pkey, _ in PLATFORMS
            if os.path.exists(os.path.join(ROOT, "out", f"email_{pkey}_{date}.html"))]


def connect():
    host, port = SMTP_HOST, SMTP_PORT
    user = os.environ.get("SMTP_USER") or MAIL_FROM
    password = os.environ.get("SMTP_PASS")
    if not password:
        print("SMTP_PASS(앱 비밀번호) 환경변수가 없습니다.", file=sys.stderr)
        sys.exit(1)
    ctx = ssl.create_default_context()
    if port == 465:
        s = smtplib.SMTP_SSL(host, port, context=ctx)
    else:
        s = smtplib.SMTP(host, port)
        s.ehlo()
        s.starttls(context=ctx)
    s.login(user, password)
    return s


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else latest_date()
    if not date:
        print("발송할 리포트가 없습니다.", file=sys.stderr)
        sys.exit(1)
    force = os.environ.get("FORCE_SEND", "").strip().lower() in ("1", "true", "yes")

    present = present_platforms(date)
    if not present:
        print("보낼 파일이 없습니다:", date, file=sys.stderr)
        sys.exit(1)

    marked_date, marked_set = read_marker()
    # 발송 대상 결정:
    #  - force            → 존재하는 전체(강제 재발송)
    #  - 새 날짜          → 존재하는 전체
    #  - 같은 날짜        → 아직 안 보낸 플랫폼만(뒤늦게 생긴 차트 자가치유, 중복 없음)
    if force:
        todo = list(present)
    elif marked_date != date:
        todo = list(present)
    else:
        todo = [p for p in present if p not in marked_set]

    if not todo:
        print(f"이미 완전 발송됨({date}: {','.join(sorted(marked_set)) or '-'}) → 건너뜀. "
              f"(강제 재발송은 FORCE_SEND=1)")
        return

    to_env = os.environ.get("MAIL_TO")
    recipients = [a.strip() for a in to_env.split(",")] if to_env else CFG["to"]

    sent_keys = []
    s = connect()
    try:
        for pkey, label in PLATFORMS:
            if pkey not in todo:
                continue
            path = os.path.join(ROOT, "out", f"email_{pkey}_{date}.html")
            with open(path, encoding="utf-8") as f:
                html = f.read()
            tag = os.environ.get("SUBJECT_TAG", "").strip()
            subject = f'{CFG["subject_prefix"]} {date} {label} Top100 리포트' + (f' {tag}' if tag else '')
            msg = MIMEText(html, "html", "utf-8")
            msg["Subject"] = str(Header(subject, "utf-8"))
            msg["From"] = formataddr((str(Header(f"게임시장조사 · {label}", "utf-8")), MAIL_FROM))
            msg["To"] = ", ".join(recipients)
            msg["Date"] = formatdate(localtime=True)
            s.sendmail(MAIL_FROM, recipients, msg.as_string())
            print(f"발송 완료 [{label}] → {', '.join(recipients)}")
            sent_keys.append(pkey)
    finally:
        s.quit()
    if not sent_keys:
        print("보낼 파일이 없습니다:", date, file=sys.stderr)
        sys.exit(1)
    # 마커 갱신: 같은 날짜면 기존 집합에 합집합(누적), 새 날짜면 이번에 보낸 것만
    newset = (marked_set | set(sent_keys)) if marked_date == date else set(sent_keys)
    write_marker(date, newset)
    print(f"마커 기록: {date}: {','.join(sorted(newset))}")


if __name__ == "__main__":
    main()
