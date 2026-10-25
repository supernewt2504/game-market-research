// 검증 게임의 미디어(아이콘/스크린샷/영상)를 스토어에서 경량으로 확보
// Google Play 이미지 CDN은 =w<px> 파라미터로 원본 용량 증가 없이 리사이즈 가능.
import gplay from 'google-play-scraper';
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const g = gplay.default || gplay;
const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');

// Google 이미지 URL 폭 제한(용량 축소)
function sized(url, w) {
  if (!url) return url;
  if (url.includes('googleusercontent.com')) {
    return url.replace(/=.*$/, '') + `=w${w}`;
  }
  return url;
}

function findAppId(snap, name) {
  for (const key of ['google_grossing', 'google_popular']) {
    const hit = (snap.charts[key] || []).find((x) => x.name.includes(name) || name.includes(x.name));
    if (hit) return hit.id;
  }
  return null;
}

async function media(name, snap) {
  let appId = findAppId(snap, name);
  if (!appId) {
    const res = await g.search({ term: name, num: 1, country: 'kr', lang: 'ko' });
    if (res[0]) appId = res[0].appId;
  }
  if (!appId) return null;
  const app = await g.app({ appId, country: 'kr', lang: 'ko' });
  return {
    appId,
    title: app.title,
    icon: sized(app.icon, 128),
    screenshots: (app.screenshots || []).slice(0, 4).map((s) => sized(s, 400)),
    video: app.video || null,
    videoImage: sized(app.videoImage, 480),
    storeUrl: app.url,
  };
}

async function main() {
  const dateArg = process.argv[2];
  const snap = JSON.parse(readFileSync(join(ROOT, 'data', 'snapshots', `${dateArg}.json`), 'utf-8'));
  const names = ['도깨비의세계', '운빨존많겜'];
  const out = {};
  for (const n of names) {
    try {
      const m = await media(n, snap);
      if (m) out[n] = m;
      console.log(n, m ? `ok (${m.screenshots.length} shots, video=${!!m.video})` : 'not found');
    } catch (e) {
      console.log(n, 'ERROR', e.message);
    }
  }
  writeFileSync(join(ROOT, 'report', 'media.json'), JSON.stringify(out, null, 2), 'utf-8');
  console.log('저장: report/media.json');
}
main();
