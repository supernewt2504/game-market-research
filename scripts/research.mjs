// 상승이유 조사 + 개발사 국적 보완 (토큰 절약: Haiku + 상한 + 캐시)
// - 국적: app_meta.json 에서 미확인 개발사만 Haiku로 일괄 보완(웹검색 없음)
// - 상승이유: 매출 NEW + 상승폭 큰 게임만(상한), 캐시 유효기간 내면 재조사 안 함
//   웹검색으로 기사 탐색 -> 없으면 스토어 업데이트 내역 근거 -> JSON 산출
// - 미디어: 조사 대상 게임의 아이콘/스크린샷/영상(스토어 CDN, 폭 제한)
// API 키(ANTHROPIC_API_KEY) 없으면 LLM 단계는 건너뜀.
import Anthropic from '@anthropic-ai/sdk';
import gplay from 'google-play-scraper';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const g = gplay.default || gplay;
const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const DATA = join(ROOT, 'data');
const cfg = JSON.parse(readFileSync(join(ROOT, 'config.json'), 'utf-8'));

const HAS_KEY = !!process.env.ANTHROPIC_API_KEY;
const client = HAS_KEY ? new Anthropic() : null;
const MODEL = cfg.research.model;

const readJson = (p, d) => (existsSync(p) ? JSON.parse(readFileSync(p, 'utf-8')) : d);
const writeJson = (p, o) => { mkdirSync(dirname(p), { recursive: true }); writeFileSync(p, JSON.stringify(o, null, 2), 'utf-8'); };

function extractJson(text) {
  if (!text) return null;
  let t = text.trim().replace(/^```(?:json)?/i, '').replace(/```$/, '').trim();
  const s = t.indexOf('{'), e = t.lastIndexOf('}');
  if (s < 0 || e < 0) return null;
  try { return JSON.parse(t.slice(s, e + 1)); } catch { return null; }
}

function finalText(msg) {
  return (msg.content || []).filter((b) => b.type === 'text').map((b) => b.text).join('\n');
}

// web_search 포함 요청(pause_turn 1회 이어받기)
async function ask(system, userText, useWeb, maxTokens = 1500) {
  const tools = useWeb
    ? [{ type: 'web_search_20250305', name: 'web_search', max_uses: cfg.research.web_search_max_uses,
         user_location: { type: 'approximate', country: 'KR' } }]
    : undefined;
  const messages = [{ role: 'user', content: userText }];
  let msg = await client.messages.create({ model: MODEL, max_tokens: maxTokens, system, messages, ...(tools ? { tools } : {}) });
  let guard = 0;
  while (msg.stop_reason === 'pause_turn' && guard++ < 2) {
    messages.push({ role: 'assistant', content: msg.content });
    msg = await client.messages.create({ model: MODEL, max_tokens: maxTokens, system, messages, ...(tools ? { tools } : {}) });
  }
  return finalText(msg);
}

const sized = (u, w) => (u && u.includes('googleusercontent.com') ? u.replace(/=.*$/, '') + `=w${w}` : u);

async function media(name, googleId) {
  try {
    let appId = googleId && !/^\d+$/.test(googleId) ? googleId : null;
    if (!appId) {
      const r = await g.search({ term: name, num: 1, country: cfg.country, lang: cfg.lang });
      appId = r[0]?.appId;
    }
    if (!appId) return {};
    const a = await g.app({ appId, country: cfg.country, lang: cfg.lang });
    return {
      icon: sized(a.icon, 128),
      screenshots: (a.screenshots || []).slice(0, 4).map((s) => sized(s, 400)),
      video: a.video || null,
      videoImage: sized(a.videoImage, 480),
      storeUrl: a.url,
      recentChanges: a.recentChanges || '',
    };
  } catch { return {}; }
}

// ---------- 1) 개발사 국적 보완 ----------
const normDev = (s) => (s || '').toLowerCase().replace(/\s+/g, ' ').trim();

async function resolveCountries(meta) {
  if (!HAS_KEY) return 0;
  const unknownDevs = [...new Set(
    Object.values(meta).filter((m) => m && m.developer && !m.country).map((m) => m.developer)
  )];
  if (!unknownDevs.length) return 0;
  const system = '너는 모바일 게임 퍼블리셔 국적 분류기다. 각 회사의 본사 국가를 ISO 3166-1 alpha-2 코드로 판단한다. 모르면 "??". 반드시 JSON 객체만 출력.';
  const resolved = {};  // normDev(name) -> code
  const CHUNK = 40;
  for (let i = 0; i < unknownDevs.length; i += CHUNK) {
    const chunk = unknownDevs.slice(i, i + CHUNK);
    const prompt = `다음 게임 개발사/퍼블리셔 각각의 본사 국가를 ISO 3166-1 alpha-2 코드로 알려줘. 모르면 "??".\n`
      + `출력은 JSON 객체 하나만: {"회사명":"KR", ...}\n목록:\n${chunk.map((d) => `- ${d}`).join('\n')}`;
    try {
      const map = extractJson(await ask(system, prompt, false, 2500)) || {};
      for (const [k, v] of Object.entries(map)) {
        if (typeof v === 'string' && /^[A-Za-z]{2}$/.test(v)) resolved[normDev(k)] = v.toUpperCase();
      }
    } catch (e) { console.log('  국적 청크 오류:', e.message); }
  }
  let n = 0;
  for (const m of Object.values(meta)) {
    if (m && m.developer && !m.country) {
      const c = resolved[normDev(m.developer)];
      if (c) { m.country = c; n++; }
    }
  }
  return n;
}

// ---------- 2) 상승이유 조사 ----------
function diffMovers(today, prev) {
  const movers = [];
  for (const key of cfg.charts) {
    if (!cfg.research.include_popular_charts && key.endsWith('popular')) continue;
    const pm = Object.fromEntries((prev.charts[key] || []).map((x) => [x.id, x.rank]));
    for (const it of today.charts[key]) {
      const pr = pm[it.id];
      let type = null, delta = 0;
      if (pr === undefined) type = 'new';
      else if (pr - it.rank >= cfg.research.rise_threshold) { type = 'up'; delta = pr - it.rank; }
      if (type) movers.push({ ...it, chart: key, changeType: type, delta });
    }
  }
  // 우선순위: 매출 > 인기, NEW > 상승, 상승폭 큰 순
  const score = (m) => (m.chart.includes('grossing') ? 1000 : 0) + (m.changeType === 'new' ? 500 : 0) + m.delta;
  movers.sort((a, b) => score(b) - score(a));
  // 같은 게임 중복 제거
  const seen = new Set(), uniq = [];
  for (const m of movers) { if (!seen.has(m.id)) { seen.add(m.id); uniq.push(m); } }
  return uniq;
}

async function researchMover(m) {
  const md = await media(m.name, m.id);
  if (!HAS_KEY) {
    return { verified: false, category: '확인 필요', short: '', summary: '', articles: [], ...md };
  }
  const chartLabel = { google_grossing: 'Google 매출', google_popular: 'Google 인기',
    apple_grossing: 'App Store 매출', apple_popular: 'App Store 인기' }[m.chart] || m.chart;
  const changeLabel = m.changeType === 'new' ? '신규 진입' : `${m.delta}계단 상승`;
  const system = '너는 한국 모바일 게임 시장 분석가다. 주어진 게임의 순위 상승/신규진입 원인을 조사한다. '
    + '먼저 web_search로 최신 한국어 기사를 찾고, 기사가 있으면 verified=true로 요약+링크를 담는다. '
    + '기사를 못 찾으면 제공된 스토어 업데이트 내역(recentChanges)을 근거로 판단하되 verified=false로 둔다. '
    + '추측만으로 verified=true를 주지 마라. 반드시 아래 JSON 하나만 출력.';
  const schema = `{"verified": true/false,
 "category": "신규 오픈|컨텐츠 업데이트|매출 이벤트|콜라보|시즌·패스|기타 중 하나",
 "short": "비고란에 넣을 한 줄 요약(40자 이내)",
 "summary": "상세 2~4문장(한국어)",
 "articles": [{"title":"기사 제목","url":"https URL"}]}`;
  const prompt = `게임: ${m.name}\n개발사: ${m.developer}\n차트: ${chartLabel}\n변동: ${changeLabel} (현재 ${m.rank}위)\n`
    + (md.recentChanges ? `스토어 최근 업데이트 내역:\n${md.recentChanges.slice(0, 600)}\n` : '')
    + `\n위 게임의 순위 상승 원인을 조사해 아래 형식의 JSON만 출력해줘:\n${schema}`;
  let r;
  try { r = extractJson(await ask(system, prompt, true)); } catch { r = null; }
  if (!r) r = { verified: false, category: '확인 필요', short: '', summary: '', articles: [] };
  r.articles = Array.isArray(r.articles) ? r.articles.filter((a) => a && a.url && /^https?:/.test(a.url)) : [];
  return { ...r, ...md };
}

async function main() {
  const date = process.argv[2];
  const snap = readJson(join(DATA, 'snapshots', `${date}.json`), null);
  if (!snap) { console.error('스냅샷 없음:', date); process.exit(1); }
  const prevDate = new Date(new Date(date).getTime() - 86400000).toISOString().slice(0, 10);
  const prev = readJson(join(DATA, 'snapshots', `${prevDate}.json`), null);

  const metaPath = join(DATA, 'app_meta.json');
  const meta = readJson(metaPath, {});
  const nC = await resolveCountries(meta);
  if (nC) { writeJson(metaPath, meta); console.log(`국적 보완: +${nC}`); }
  else console.log(HAS_KEY ? '국적 보완: 추가 없음' : '국적 보완: 건너뜀(API 키 없음)');

  const reasonsPath = join(DATA, 'reasons', `${date}.json`);
  const cachePath = join(DATA, 'reasons_cache.json');
  const cache = readJson(cachePath, {});
  const reasons = {};

  if (!prev) {
    console.log('전일 스냅샷 없음 → 상승이유 조사 생략(첫날).');
    writeJson(reasonsPath, reasons);
    return;
  }

  const movers = diffMovers(snap, prev);
  const cap = cfg.research.max_research_per_day;
  const ttl = cfg.research.reason_cache_ttl_days * 86400000;
  let used = 0;
  console.log(`변동 대상 ${movers.length}건, 상한 ${cap}`);
  for (const m of movers) {
    const cached = cache[m.id];
    if (cached && cached.verified && (Date.now() - new Date(cached.researchedAt).getTime()) < ttl) {
      reasons[m.id] = cached.data;  // 재사용(토큰 0)
      continue;
    }
    if (used >= cap) continue;
    used++;
    const data = await researchMover(m);
    reasons[m.id] = data;
    cache[m.id] = { researchedAt: new Date().toISOString(), verified: !!data.verified, data };
  }
  writeJson(reasonsPath, reasons);
  writeJson(cachePath, cache);
  console.log(`조사 완료: 신규호출 ${used}건, 캐시재사용 ${Object.keys(reasons).length - used}건`);
}
main().catch((e) => { console.error(e); process.exit(1); });
