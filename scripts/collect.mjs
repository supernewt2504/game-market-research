// 게임시장조사 - 일일 차트 수집기
// Apple App Store(공식 RSS) + Google Play(google-play-scraper), 대한민국 / 게임 카테고리
// 4개 차트 각 Top 100 -> data/snapshots/<YYYY-MM-DD>.json
import gplay from 'google-play-scraper';
import { writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const g = gplay.default || gplay;
const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const COUNTRY = 'kr';
const GAME_GENRE_APPLE = 6014; // Apple Games genre id
const LIMIT = 100;

// ---------- Apple (iTunes RSS) ----------
async function appleChart(feed) {
  const url = `https://itunes.apple.com/${COUNTRY}/rss/${feed}/limit=${LIMIT}/genre=${GAME_GENRE_APPLE}/json`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Apple ${feed} HTTP ${res.status}`);
  const data = await res.json();
  const entries = data.feed.entry || [];
  return entries.map((e, i) => ({
    rank: i + 1,
    name: e['im:name']?.label ?? '',
    id: e.id?.attributes?.['im:id'] ?? '',
    developer: e['im:artist']?.label ?? '',
    url: e.id?.label ?? '',
  }));
}

// ---------- Google Play ----------
async function googleChart(collection) {
  const r = await g.list({
    collection,
    category: g.category.GAME,
    country: COUNTRY,
    lang: 'ko',       // 한국어 명칭 우선(있으면 한글 타이틀 반환)
    num: LIMIT,
  });
  return r.map((a, i) => ({
    rank: i + 1,
    name: a.title,
    id: a.appId,
    developer: a.developer ?? '',
    url: a.url ?? `https://play.google.com/store/apps/details?id=${a.appId}`,
  }));
}

// 실행 시각이 아니라 "논리적 수집일"을 반환(지연 실행으로 날짜가 밀리는 것 방지).
// 정오(KST) 이전 실행 = 예약이 자정을 넘겨 지연된 경우로 보고 전날로 귀속.
function logicalKstDate(now = new Date()) {
  const kst = new Date(now.getTime() + 9 * 3600 * 1000);
  if (kst.getUTCHours() < 12) kst.setUTCDate(kst.getUTCDate() - 1);
  return kst.toISOString().slice(0, 10);
}

async function main() {
  // 날짜 우선순위: 인자 > 논리적 KST 날짜(실행 시각 무관)
  const date = process.argv[2] || logicalKstDate();

  // 백업 슬롯(IS_BACKUP)에서 해당 날짜 스냅샷이 이미 있으면 재수집 생략(덮어쓰기/재조사 방지)
  const snapPath = join(ROOT, 'data', 'snapshots', `${date}.json`);
  if (process.env.IS_BACKUP === 'true' && existsSync(snapPath) && process.env.FORCE_COLLECT !== 'true') {
    console.log(`백업 슬롯: ${date} 스냅샷이 이미 있음 → 수집 생략`);
    return;
  }

  const now = new Date();
  const [apple_popular, apple_grossing, google_popular, google_grossing] = await Promise.all([
    appleChart('topfreeapplications'),
    appleChart('topgrossingapplications'),
    googleChart(g.collection.TOP_FREE),
    googleChart(g.collection.GROSSING),
  ]);

  const snapshot = {
    date,
    collectedAt: now.toISOString(),
    country: COUNTRY,
    charts: { google_popular, google_grossing, apple_popular, apple_grossing },
  };

  const counts = Object.fromEntries(
    Object.entries(snapshot.charts).map(([k, v]) => [k, v.length])
  );
  console.log('수집 완료:', JSON.stringify(counts));

  mkdirSync(join(ROOT, 'data', 'snapshots'), { recursive: true });
  writeFileSync(snapPath, JSON.stringify(snapshot, null, 2), 'utf-8');
  console.log('저장:', snapPath);
}

main().catch((e) => {
  console.error('수집 실패:', e);
  process.exit(1);
});
