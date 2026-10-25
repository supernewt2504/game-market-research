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


def kst_today():
    return (datetime.now(timezone.utc) + timedelta(hours=9)).date()


PLATFORMS = [("google", "Google Play"), ("apple", "App Store")]


def latest_date():
    import glob
    files = sorted(glob.glob(os.path.join(ROOT, "out", "email_google_*.html")))
    if not files:
        files = sorted(glob.glob(os.path.join(ROOT, "out", "email_apple_*.html")))
    if not files:
        return None
    return os.path.basename(files[-1]).rsplit("_", 1)[1][:-5]  # email_google_<date>.html -> date


def connect():
    host, port = CFG["smtp_host"], int(CFG["smtp_port"])
    user = os.environ.get("SMTP_USER") or CFG["from"]
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
    to_env = os.environ.get("MAIL_TO")
    recipients = [a.strip() for a in to_env.split(",")] if to_env else CFG["to"]

    sent = 0
    s = connect()
    try:
        for pkey, label in PLATFORMS:
            path = os.path.join(ROOT, "out", f"email_{pkey}_{date}.html")
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as f:
                html = f.read()
            tag = os.environ.get("SUBJECT_TAG", "").strip()
            subject = f'{CFG["subject_prefix"]} {date} {label} Top100 리포트' + (f' {tag}' if tag else '')
            msg = MIMEText(html, "html", "utf-8")
            msg["Subject"] = str(Header(subject, "utf-8"))
            msg["From"] = formataddr((str(Header(f"게임시장조사 · {label}", "utf-8")), CFG["from"]))
            msg["To"] = ", ".join(recipients)
            msg["Date"] = formatdate(localtime=True)
            s.sendmail(CFG["from"], recipients, msg.as_string())
            print(f"발송 완료 [{label}] → {', '.join(recipients)}")
            sent += 1
    finally:
        s.quit()
    if sent == 0:
        print("보낼 파일이 없습니다:", date, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
