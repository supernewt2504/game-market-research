// 앱 메타데이터 수집기: 런칭일자 + 개발사 국적(국기)
// - Google: google-play-scraper app() -> released, developerAddress(국가 추정)
// - Apple : iTunes lookup API -> releaseDate, artistName
// - 결과를 data/app_meta.json 에 캐시 (한 번 받은 앱은 재조회 안 함 => 토큰/시간 절약)
import gplay from 'google-play-scraper';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const g = gplay.default || gplay;
const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const DATA = join(ROOT, 'data');

// 주요 퍼블리셔 국적 시드(이름 부분일치, 소문자). 나머지는 주소/후순위로 추정.
const DEV_SEED = [
  // 한국
  ['ncsoft', 'KR'], ['netmarble', 'KR'], ['nexon', 'KR'], ['kakao games', 'KR'], ['kakaogames', 'KR'],
  ['com2us', 'KR'], ['pearl abyss', 'KR'], ['smilegate', 'KR'], ['devsisters', 'KR'], ['111%', 'KR'],
  ['111 percent', 'KR'], ['haegin', 'KR'], ['line games', 'KR'], ['wemade', 'KR'], ['npixel', 'KR'],
  ['shift up', 'KR'], ['gravity', 'KR'], ['neowiz', 'KR'], ['webzen', 'KR'], ['joycity', 'KR'],
  ['supercent', 'KR'], ['playwith', 'KR'], ['superfast', 'KR'], ['super fast', 'KR'], ['111퍼센트', 'KR'],
  ['dreamidea', 'KR'], ['noriworks', 'KR'], ['actnine', 'KR'], ['clover games', 'KR'], ['vaned', 'KR'],
  ['morefun', 'KR'], ['snowpipe', 'KR'], ['hundredsoft', 'KR'], ['rpg factory', 'KR'],
  // 중국
  ['tencent', 'CN'], ['netease', 'CN'], ['mihoyo', 'CN'], ['hoyoverse', 'CN'], ['century games', 'CN'],
  ['papergames', 'CN'], ['microfun', 'CN'], ['funplus', 'CN'], ['lilith', 'CN'], ['igg', 'CN'],
  ['4399', 'CN'], ['dragonest', 'CN'], ['eyougame', 'CN'], ['gtarcade', 'CN'], ['qookka', 'CN'],
  ['diandian', 'CN'], ['zuoyebang', 'CN'], ['kuro game', 'CN'], ['kuro games', 'CN'], ['habby', 'CN'],
  ['yoozoo', 'CN'], ['37games', 'CN'], ['37 games', 'CN'], ['joynews', 'CN'], ['readygo', 'CN'],
  ['chaopiao', 'CN'], ['xd ', 'CN'], ['chillyroom', 'CN'],
  // 일본
  ['bandai namco', 'JP'], ['sega', 'JP'], ['square enix', 'JP'], ['cygames', 'JP'], ['mixi', 'JP'],
  ['konami', 'JP'], ['colopl', 'JP'], ['gumi', 'JP'], ['aniplex', 'JP'], ['dena', 'JP'], ['gree', 'JP'],
  ['capcom', 'JP'], ['level-5', 'JP'], ['kairosoft', 'JP'], ['yostar', 'JP'],
  // 미국/유럽/기타
  ['roblox', 'US'], ['king', 'US'], ['scopely', 'US'], ['zynga', 'US'], ['jam city', 'US'],
  ['electronic arts', 'US'], ['ea ', 'US'], ['niantic', 'US'], ['activision', 'US'], ['supercell', 'FI'],
  ['rovio', 'FI'], ['dream games', 'TR'], ['peak', 'TR'], ['moon active', 'IL'], ['playtika', 'IL'],
  ['saygames', 'CY'], ['voodoo', 'FR'], ['homa', 'FR'], ['playrix', 'IE'], ['miniclip', 'CH'],
  ['gameloft', 'FR'], ['outfit7', 'CY'], ['garena', 'SG'], ['sea limited', 'SG'], ['krafton', 'KR'],
];

// 주소 문자열 -> 국가코드 추정
const ADDR_COUNTRY = [
  ['south korea', 'KR'], ['korea', 'KR'], ['대한민국', 'KR'], ['republic of korea', 'KR'],
  ['china', 'CN'], ['中国', 'CN'], ['hong kong', 'HK'], ['singapore', 'SG'], ['japan', 'JP'], ['日本', 'JP'],
  ['united states', 'US'], ['usa', 'US'], ['finland', 'FI'], ['turkey', 'TR'], ['türkiye', 'TR'],
  ['israel', 'IL'], ['cyprus', 'CY'], ['france', 'FR'], ['ireland', 'IE'], ['germany', 'DE'],
  ['united kingdom', 'GB'], ['taiwan', 'TW'], ['vietnam', 'VN'], ['canada', 'CA'], ['netherlands', 'NL'],
  ['switzerland', 'CH'], ['sweden', 'SE'], ['belarus', 'BY'], ['malta', 'MT'], ['spain', 'ES'],
];

function seedCountry(name) {
  const n = (name || '').toLowerCase();
  for (const [k, c] of DEV_SEED) if (n.includes(k)) return c;
  return null;
}
function addrCountry(addr) {
  const a = (addr || '').toLowerCase();
  for (const [k, c] of ADDR_COUNTRY) if (a.includes(k)) return c;
  return null;
}
function sizedIcon(url, w = 48) {
  return (url && url.includes('googleusercontent.com')) ? url.replace(/=.*$/, '') + `=w${w}` : url;
}
// 원스토어·갤럭시 게임명↔구글 플레이 매칭용 정규화
const normName = (n) => (n || '').toLowerCase()
  .replace(/for\s*onestore|for\s*samsung/g, '').replace(/•••|\.\.\.|…/g, '')
  .replace(/[^0-9a-z가-힣]/g, '');
function normDate(s) {
  if (!s) return null;
  // ISO (Apple)
  const iso = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
  if (iso) return `${iso[1]}.${iso[2]}.${iso[3]}`;
  // "Oct 13, 2026" (Google en)
  const d = new Date(s);
  if (!isNaN(d)) {
    const y = d.getFullYear(), m = String(d.getMonth() + 1).padStart(2, '0'), day = String(d.getDate()).padStart(2, '0');
    return `${y}.${m}.${day}`;
  }
  // "2026. 10. 13." (Google ko)
  const ko = /(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})/.exec(s);
  if (ko) return `${ko[1]}.${String(ko[2]).padStart(2, '0')}.${String(ko[3]).padStart(2, '0')}`;
  return s;
}

async function pool(items, size, worker) {
  const out = [];
  let i = 0;
  async function run() {
    while (i < items.length) {
      const idx = i++;
      out[idx] = await worker(items[idx]).catch(() => null);
    }
  }
  await Promise.all(Array.from({ length: size }, run));
  return out;
}

async function appleLookup(ids, meta) {
  // 최대 80개씩 묶어 조회. 기존 국적은 보존하고 아이콘만 채움.
  for (let i = 0; i < ids.length; i += 80) {
    const batch = ids.slice(i, i + 80);
    const url = `https://itunes.apple.com/lookup?id=${batch.join(',')}&country=kr`;
    try {
      const res = await fetch(url);
      const data = await res.json();
      for (const r of data.results || []) {
        const id = String(r.trackId);
        const prev = meta[id] || {};
        meta[id] = {
          released: prev.released || normDate(r.releaseDate),
          developer: r.artistName || prev.developer,
          country: prev.country || seedCountry(r.artistName),
          icon: r.artworkUrl100 || r.artworkUrl60 || prev.icon,
          source: 'apple',
        };
      }
    } catch (e) { /* skip */ }
  }
}

async function main() {
  const date = process.argv[2];
  const snap = JSON.parse(readFileSync(join(DATA, 'snapshots', `${date}.json`), 'utf-8'));
  const metaPath = join(DATA, 'app_meta.json');
  const meta = existsSync(metaPath) ? JSON.parse(readFileSync(metaPath, 'utf-8')) : {};

  // 고유 앱 수집
  const googleIds = new Set(), appleIds = new Set();
  for (const key of Object.keys(snap.charts)) {
    if (key.startsWith('onestore_') || key.startsWith('galaxy_')) continue;  // OCR 수집(앱ID 없음) → 메타 조회 대상 아님
    for (const it of snap.charts[key]) {
      const isApple = /^\d+$/.test(it.id);
      if (isApple) appleIds.add(it.id); else googleIds.add(it.id);
    }
  }
  // 미캐시 또는 아이콘 없는 항목만 조회
  const needGoogle = [...googleIds].filter((id) => !meta[id] || !meta[id].icon);
  const needApple = [...appleIds].filter((id) => !meta[id] || !meta[id].icon);
  console.log(`캐시됨 ${Object.keys(meta).length} | 보강대상 Google ${needGoogle.length} / Apple ${needApple.length}`);

  // Google: app() 병렬(동시 8). 기존 국적 보존, 아이콘 추가.
  await pool(needGoogle, 8, async (id) => {
    const a = await g.app({ appId: id, country: 'kr', lang: 'ko' });
    const prev = meta[id] || {};
    meta[id] = {
      released: prev.released || normDate(a.released),
      developer: a.developer || prev.developer,
      country: prev.country || seedCountry(a.developer) || addrCountry(a.developerAddress),
      icon: sizedIcon(a.icon, 48),
      source: 'google',
    };
  });
  // Apple: lookup 배치
  if (needApple.length) await appleLookup(needApple, meta);

  // 원스토어·갤럭시: 앱ID가 없으므로 게임명으로 Google Play 검색해 아이콘 보강(캐시: 합성 id)
  const krItems = [], krSeen = new Set();
  for (const key of Object.keys(snap.charts)) {
    if (!(key.startsWith('onestore_') || key.startsWith('galaxy_'))) continue;
    for (const it of snap.charts[key]) {
      if (krSeen.has(it.id)) continue;
      krSeen.add(it.id);
      const m = meta[it.id];
      // 아이콘 없는 항목만 검색(국적은 주소 미제공이라 Haiku 판별기(research)가 개발사명으로 채움)
      if (!m || !m.icon) krItems.push({ id: it.id, name: it.name });
    }
  }
  if (krItems.length) {
    console.log(`국내스토어 보강대상(아이콘/국적) ${krItems.length}`);
    let gotIcon = 0, gotCty = 0;
    const sleep = (ms) => new Promise((res) => setTimeout(res, ms));
    const retry = async (fn, n = 3) => {
      for (let i = 0; i < n; i++) { try { const v = await fn(); if (v) return v; } catch { /* throttle */ } await sleep(1000 * (i + 1)); }
      return null;
    };
    await pool(krItems, 4, async ({ id, name }) => {
      const q = normName(name);
      if (!q) return;
      const list = await retry(async () => { const x = await g.search({ term: name, num: 3, country: 'kr', lang: 'ko' }); return x && x.length ? x : null; }) || [];
      // 제목 정규화 일치(완전일치 우선, 없으면 앞 6자 접두 겹침)로 오매칭 방지
      const hit = list.find((a) => normName(a.title) === q)
        || list.find((a) => { const t = normName(a.title); return t && (t.includes(q.slice(0, 6)) || q.includes(t.slice(0, 6))); });
      if (!hit || !hit.appId) return;
      // 앱 상세로 개발사 주소(→국가)·런칭일·아이콘 확보
      const a = await retry(async () => g.app({ appId: hit.appId, country: 'kr', lang: 'ko' }));
      const prev = meta[id] || {};
      meta[id] = { ...prev,
        icon: prev.icon || sizedIcon((a && a.icon) || hit.icon, 48),
        developer: prev.developer || (a && a.developer) || hit.developer,
        country: prev.country || seedCountry((a && a.developer) || hit.developer) || addrCountry(a && a.developerAddress),
        released: prev.released || (a ? normDate(a.released) : prev.released),
        url: (a && a.url) || hit.url || prev.url,
        appId: hit.appId, source: 'kr-google-match', title: (a && a.title) || hit.title };
      if (meta[id].icon) gotIcon++;
      if (meta[id].country) gotCty++;
    });
    console.log(`국내스토어 매칭: 아이콘 ${gotIcon}, 국적 ${gotCty} / 대상 ${krItems.length}`);
  }

  mkdirSync(DATA, { recursive: true });
  writeFileSync(metaPath, JSON.stringify(meta, null, 2), 'utf-8');

  // 커버리지 리포트
  const all = [...googleIds, ...appleIds];
  const withDate = all.filter((id) => meta[id]?.released).length;
  const withCty = all.filter((id) => meta[id]?.country).length;
  console.log(`런칭일 ${withDate}/${all.length} | 국적 ${withCty}/${all.length}`);
}
main().catch((e) => { console.error(e); process.exit(1); });
