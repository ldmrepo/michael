import dotenv from 'dotenv';
dotenv.config(); // .env 파일 로드

import { Memory } from '../src/brain/memory.js';
import { loadMemoryConfig, type MichaelMemoryConfig } from '../src/memory-new/config.js';
import path from 'path';
import fs from 'fs';

const testDir = './data-test-vector';
const sharedModelDir = './data/models'; // 공유 모델 캐시

async function main() {
  console.log('🧪 벡터 검색 엔진 테스트 시작\n');

  // 테스트 디렉토리 정리
  if (fs.existsSync(testDir)) {
    fs.rmSync(testDir, { recursive: true });
  }
  fs.mkdirSync(testDir, { recursive: true });

  const dbPath = path.join(testDir, 'memory.db');
  const memory = new Memory(dbPath);

  // 1. 벡터 검색 초기화
  console.log('1️⃣ 벡터 검색 초기화...');

  // 공유 모델 캐시 디렉토리 생성
  fs.mkdirSync(sharedModelDir, { recursive: true });

  const config = loadMemoryConfig(testDir);
  // 공유 모델 디렉토리 사용
  if (config.memory.search.local) {
    config.memory.search.local.modelCacheDir = sharedModelDir;
  }
  console.log(`   Provider: ${config.memory.search.provider}`);
  console.log(`   Model: ${config.memory.search.model}`);
  console.log(`   Model Cache: ${config.memory.search.local?.modelCacheDir}`);

  try {
    await memory.initializeVectorSearch(config);
    console.log('   ✅ 초기화 성공\n');
  } catch (error) {
    console.error(`   ❌ 초기화 실패: ${error}`);
    await memory.close();
    fs.rmSync(testDir, { recursive: true });
    process.exit(1);
  }

  // 2. 테스트 메시지 저장
  console.log('2️⃣ 테스트 메시지 저장...');
  const testMessages = [
    { role: 'user', content: '나는 서울에 살고 있어' },
    { role: 'assistant', content: '서울에 사시는군요! 좋은 곳이죠.' },
    { role: 'user', content: '내 취미는 등산이야' },
    { role: 'assistant', content: '등산 좋아하시는군요! 건강에도 좋죠.' },
    { role: 'user', content: '오늘 날씨가 좋아서 한강에 갔어' },
    { role: 'assistant', content: '한강 산책 좋죠! 날씨가 좋으니 기분도 좋으셨겠어요.' },
    { role: 'user', content: '나는 커피를 좋아해' },
    { role: 'assistant', content: '커피 좋아하시는군요! 어떤 종류를 좋아하세요?' },
    { role: 'user', content: '프로그래밍 공부를 하고 있어' },
    { role: 'assistant', content: '프로그래밍 공부 중이시군요! 어떤 언어를 배우고 계세요?' },
  ];

  const userId = 'test-user';
  memory.ensureUser(userId);

  for (const msg of testMessages) {
    await memory.saveMessage(userId, msg.role as 'user' | 'assistant', msg.content);
  }
  console.log(`   ✅ ${testMessages.length}개 메시지 저장 완료\n`);

  // 3. 메시지 → 벡터 인덱싱
  console.log('3️⃣ 메시지 벡터 인덱싱...');
  const startTime = Date.now();
  await memory.syncMessagesToChunks(userId);
  const indexTime = Date.now() - startTime;
  console.log(`   ✅ 인덱싱 완료 (${indexTime}ms)\n`);

  // 4. 벡터 검색 테스트
  console.log('4️⃣ 벡터 검색 테스트...\n');

  const testQueries = [
    '어디 살아?',           // "서울에 살고 있어" 매칭 기대
    '무슨 운동 좋아해?',     // "등산" 매칭 기대
    '뭐 마셔?',            // "커피" 매칭 기대
    '뭐 공부해?',          // "프로그래밍" 매칭 기대
  ];

  for (const query of testQueries) {
    console.log(`   🔍 Query: "${query}"`);
    const results = await memory.searchMessagesVector(userId, query, {
      maxResults: 2,
      minScore: 0.0,
    });

    if (results.length === 0) {
      console.log('      결과 없음\n');
    } else {
      for (const result of results) {
        const preview = result.content.length > 40
          ? result.content.substring(0, 40) + '...'
          : result.content;
        console.log(`      📝 [${(result.score * 100).toFixed(1)}%] ${result.role}: "${preview}"`);
      }
      console.log('');
    }
  }

  // 5. 정리
  await memory.close();
  fs.rmSync(testDir, { recursive: true });

  console.log('✅ 테스트 완료!');
}

main().catch(console.error);
