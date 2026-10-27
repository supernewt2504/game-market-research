// 게임시장조사 - 일일 차트 수집기
// Apple App Store(공식 RSS) + Google Play(google-play-scraper), 대한민국 / 게임 카테고리
// 4개 차트 각 Top 100 -> data/snapshots/<YYYY-MM-DD>.json
import gplay from 'google-play-scraper';
import { writeFileSync, mkdirSync } from 'node:fs';
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

async function main() {
  const now = new Date();
  // KST 기준 날짜
  const kst = new Date(now.getTime() + 9 * 3600 * 1000);
  const date = kst.toISOString().slice(0, 10);

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
  const out = join(ROOT, 'data', 'snapshots', `${date}.json`);
  writeFileSync(out, JSON.stringify(snapshot, null, 2), 'utf-8');
  console.log('저장:', out);
}

main().catch((e) => {
  console.error('수집 실패:', e);
  process.exit(1);
});
