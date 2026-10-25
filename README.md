# 게임시장조사 (Game Market Research)

대한민국 Google Play · App Store **게임 Top 100(인기/매출)** 일일 모니터링 & 자동 메일 리포트.

- 전일 대비 **변동**(상승 🔴 / 하락 🔵), 매출 **NEW**, **피쳐드** 표기
- 개발사 **국기** + **런칭일**
- 상승·신규 게임의 **상승이유**(기사 링크·이미지·영상), 근거 **확인/미확인**
- 매일 밤 수집 → **다음날 아침 메일 발송** (GitHub Actions)

설치·배포·설정은 **[SETUP.md](SETUP.md)** 참고.

```bash
npm install
DATE=$(TZ=Asia/Seoul date +%F)
node scripts/collect.mjs && node scripts/enrich.mjs "$DATE" \
  && node scripts/research.mjs "$DATE" && python3 scripts/generate_report.py "$DATE"
open docs/daily/$DATE.html
```
