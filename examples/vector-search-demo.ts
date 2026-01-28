/**
 * Vector Search 데모
 *
 * Moltbot 벡터 검색 엔진을 통합한 Michael의 의미적 검색 기능을 시연합니다.
 */

import { Memory } from '../src/brain/memory.js';
import { loadMemoryConfig } from '../src/memory-new/config.js';
import { log } from '../src/utils/logger.js';

async function main() {
  console.log('🚀 Michael Vector Search Demo\n');

  // 1. Memory 초기화
  const memory = new Memory('./data/memory.db');
  const config = loadMemoryConfig('./data');

  // 2. 벡터 검색 초기화
  console.log('⏳ Initializing vector search engine...');
  await memory.initializeVectorSearch(config);
  console.log('✅ Vector search engine ready\n');

  // 3. 테스트 메시지 생성
  const userId = 'demo-user';
  const testMessages = [
    '내일 회의 준비해줘',
    '회의실 예약 완료했어',
    '오늘 날씨가 정말 좋네',
    '미팅 자료 작성 중이야',
    '저녁에 친구 만나기로 했어',
    '프로젝트 마감이 다음 주야',
    '점심 뭐 먹을지 고민 중',
    '회의 시간 변경 가능해?',
  ];

  console.log('📝 Creating test messages...');
  for (const msg of testMessages) {
    await memory.saveMessage(userId, 'user', msg);
  }
  console.log(`✅ Created ${testMessages.length} test messages\n`);

  // 4. Messages → Chunks 인덱싱
  console.log('🔄 Indexing messages with embeddings...');
  await memory.syncMessagesToChunks(userId);
  console.log('✅ Indexing complete\n');

  // 5. 벡터 검색 테스트
  console.log('🔍 Testing vector search:\n');

  const queries = [
    '회의 관련 내용',
    '날씨 이야기',
    '저녁 약속',
  ];

  for (const query of queries) {
    console.log(`Query: "${query}"`);
    console.log('─'.repeat(50));

    const results = await memory.searchMessagesVector(userId, query, {
      maxResults: 3,
      minScore: 0.5,
    });

    if (results.length === 0) {
      console.log('  (No results found)\n');
      continue;
    }

    results.forEach((msg, index) => {
      console.log(`  ${index + 1}. [Score: ${(msg.score * 100).toFixed(0)}%] ${msg.content}`);
    });
    console.log('');
  }

  // 6. 기존 FTS5 검색과 비교
  console.log('\n📊 Comparison: FTS5 vs Vector Search\n');

  const comparisonQuery = '회의';
  console.log(`Query: "${comparisonQuery}"`);
  console.log('─'.repeat(50));

  console.log('\n[FTS5 Keyword Search]');
  const ftsResults = await memory.searchMessages(userId, comparisonQuery);
  ftsResults.slice(0, 3).forEach((msg, index) => {
    console.log(`  ${index + 1}. ${msg.content}`);
  });

  console.log('\n[Vector Semantic Search]');
  const vectorResults = await memory.searchMessagesVector(userId, comparisonQuery, {
    maxResults: 3,
  });
  vectorResults.forEach((msg, index) => {
    console.log(`  ${index + 1}. [Score: ${(msg.score * 100).toFixed(0)}%] ${msg.content}`);
  });

  // 7. 정리
  await memory.close();
  console.log('\n✅ Demo complete!');
}

main().catch((error) => {
  console.error('❌ Demo failed:', error);
  process.exit(1);
});
