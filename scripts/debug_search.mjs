// 웹검색 도구 동작 진단: 모델별로 web_search 결과/에러를 그대로 출력
import Anthropic from '@anthropic-ai/sdk';
const client = new Anthropic();
const model = process.argv[2] || 'claude-haiku-5-5';
try {
  const msg = await client.messages.create({
    model, max_tokens: 1024,
    messages: [{ role: 'user', content: '도깨비의세계라는 한국 모바일 게임이 최근 구글플레이 매출 1위에 오른 이유를 최신 기사로 웹검색해서 알려줘.' }],
    tools: [{ type: 'web_search_20250305', name: 'web_search', max_uses: 3, user_location: { type: 'approximate', country: 'KR' } }],
  });
  console.log('MODEL', model, '| stop_reason', msg.stop_reason);
  for (const b of msg.content) {
    if (b.type === 'web_search_tool_result') {
      const c = b.content;
      if (Array.isArray(c)) console.log('SEARCH_RESULTS', c.length, '| 예:', (c[0] && c[0].title) || '');
      else console.log('SEARCH_ERROR', JSON.stringify(c));
    } else if (b.type === 'server_tool_use') {
      console.log('SEARCH_QUERY', JSON.stringify(b.input));
    } else if (b.type === 'text') {
      console.log('TEXT', b.text.slice(0, 200));
    } else {
      console.log('BLOCK', b.type);
    }
  }
} catch (e) {
  console.log('ERROR status=', e.status, '| name=', e.name, '| msg=', e.message);
}
