// 수정된 설정으로 상승이유 조사 JSON이 정상 산출되는지 확인
import Anthropic from '@anthropic-ai/sdk';
const client = new Anthropic();
const MODEL = process.argv[2] || 'claude-haiku-5-5';

function extractJson(text) {
  if (!text) return null;
  let t = text.trim().replace(/^```(?:json)?/i, '').replace(/```$/, '').trim();
  const s = t.indexOf('{'), e = t.lastIndexOf('}');
  if (s < 0 || e < 0) return null;
  try { return JSON.parse(t.slice(s, e + 1)); } catch { return null; }
}

const system = '너는 한국 모바일 게임 시장 분석가다. web_search로 최신 한국어 기사를 찾고, 기사가 있으면 verified=true로 요약+링크. '
  + '매우 중요: 검색 끝나면 설명 문장 없이 오직 JSON 객체 하나만 출력(코드펜스 금지).';
const schema = '{"verified":true/false,"category":"신규 오픈|컨텐츠 업데이트|매출 이벤트|기타","short":"한 줄","summary":"2~4문장","articles":[{"title":"","url":"https.."}]}';
const prompt = `게임: 도깨비의세계\n개발사: 카카오게임즈\n차트: Google 매출\n변동: 신규 진입 (현재 1위)\n위 게임의 순위 상승 원인을 조사해 아래 JSON만 출력:\n${schema}`;

try {
  const messages = [{ role: 'user', content: prompt }];
  const base = { model: MODEL, max_tokens: 4000, system, output_config: { effort: 'low' },
    tools: [{ type: 'web_search_20250305', name: 'web_search', max_uses: 3, user_location: { type: 'approximate', country: 'KR' } }] };
  let msg = await client.messages.create({ ...base, messages });
  let guard = 0;
  while (msg.stop_reason === 'pause_turn' && guard++ < 3) {
    messages.push({ role: 'assistant', content: msg.content });
    msg = await client.messages.create({ ...base, messages });
  }
  const text = (msg.content || []).filter((b) => b.type === 'text').map((b) => b.text).join('\n');
  console.log('MODEL', MODEL, '| stop', msg.stop_reason, '| usage', JSON.stringify(msg.usage?.output_tokens));
  const j = extractJson(text);
  if (j) console.log('PARSED OK | verified=', j.verified, '| category=', j.category, '| articles=', (j.articles || []).length, '| short=', j.short);
  else console.log('PARSE FAIL | text head:', text.slice(0, 200));
} catch (e) {
  console.log('ERROR status=', e.status, '| msg=', e.message);
}
