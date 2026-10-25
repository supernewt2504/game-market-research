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


def latest_report():
    import glob
    files = sorted(glob.glob(os.path.join(ROOT, "out", "email_*.html")))
    return files[-1] if files else None


def main():
    if len(sys.argv) > 1:
        date = sys.argv[1]
        html_path = os.path.join(ROOT, "out", f"email_{date}.html")
    else:
        # 인자 없으면 가장 최근 리포트 발송 (cron 타이밍 안전)
        html_path = latest_report()
        date = os.path.basename(html_path)[6:-5] if html_path else str(kst_today())
    if not html_path or not os.path.exists(html_path):
        print("이메일용 리포트 없음:", html_path, file=sys.stderr)
        sys.exit(1)
    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    user = os.environ.get("SMTP_USER") or CFG["from"]
    password = os.environ.get("SMTP_PASS")
    if not password:
        print("SMTP_PASS(앱 비밀번호) 환경변수가 없습니다.", file=sys.stderr)
        sys.exit(1)
    to_env = os.environ.get("MAIL_TO")
    recipients = [a.strip() for a in to_env.split(",")] if to_env else CFG["to"]

    subject = f'{CFG["subject_prefix"]} {date} 게임 Top100 리포트'
    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = str(Header(subject, "utf-8"))
    msg["From"] = formataddr((str(Header("게임시장조사", "utf-8")), CFG["from"]))
    msg["To"] = ", ".join(recipients)
    msg["Date"] = formatdate(localtime=True)

    host, port = CFG["smtp_host"], int(CFG["smtp_port"])
    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx) as s:
            s.login(user, password)
            s.sendmail(CFG["from"], recipients, msg.as_string())
    else:  # 587 STARTTLS
        with smtplib.SMTP(host, port) as s:
            s.ehlo()
            s.starttls(context=ctx)
            s.login(user, password)
            s.sendmail(CFG["from"], recipients, msg.as_string())
    print(f"발송 완료 → {', '.join(recipients)} (제목: {subject})")


if __name__ == "__main__":
    main()
