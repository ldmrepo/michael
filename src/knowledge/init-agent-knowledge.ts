/**
 * Agent Knowledge Bootstrap
 *
 * 에이전트별 NLM 노트북 자동 생성 + Foundational Knowledge 시딩
 * KnowledgeManager.getClient()로 노트북 생성/로드
 *
 * AGENT_REGISTRY에 정의된 14개 에이전트 중
 * tools[]이 있는(실행 가능한) 에이전트만 노트북 생성
 *
 * Foundational Knowledge:
 * - knowledge/{agent.knowledgeDir}/foundational.md 파일 존재 시 자동 시딩
 * - [Foundational] 접두사 source가 이미 있으면 skip (idempotent)
 */

import { readFileSync, existsSync } from 'fs';
import path from 'path';
import { log } from '../utils/logger.js';
import type { KnowledgeManager } from './knowledge-manager.js';
import type { NlmClient } from './nlm-client.js';

export interface AgentDefinition {
  id: string;
  name: string;
  team: string;
  role: string;
  instructions: string;
  tools: Array<{ script: string; skillDir: string }>;
  knowledgeDir: string;
}

export const FOUNDATIONAL_PREFIX = '[Foundational]';

/**
 * 마이클 본체 + 에이전트별 NLM 노트북 자동 생성/로드 + Foundational Knowledge 시딩
 *
 * @param km KnowledgeManager 인스턴스
 * @returns 생성/로드된 에이전트 이름 배열
 */
export async function initAgentKnowledge(km: KnowledgeManager): Promise<string[]> {
  const initialized: string[] = [];

  // 마이클 본체 노트북 생성/로드
  try {
    const michaelClient = await km.getClient('michael');
    const michaelAgent: AgentDefinition = {
      id: 'michael',
      name: 'Michael',
      team: 'execution',
      role: '24시간 AI 자산관리 전문가',
      instructions: '',
      tools: [],
      knowledgeDir: 'knowledge/michael/',
    };
    await seedFoundationalKnowledge(michaelClient, michaelAgent);
    initialized.push('michael');
  } catch (e) {
    log('warn', `⚠️ Failed to init knowledge for michael: ${e}`);
  }

  log('info', `📓 Agent knowledge initialized: ${initialized.length} notebooks`);
  return initialized;
}

/**
 * Foundational Knowledge 시딩 (idempotent)
 *
 * 1. listSources()로 [Foundational] source 존재 여부 확인
 * 2. 이미 있으면 skip
 * 3. 없으면 knowledge/{knowledgeDir}/foundational.md 읽어서 addSource
 *
 * @returns true if seeded, false if skipped
 */
export async function seedFoundationalKnowledge(
  client: NlmClient,
  agent: AgentDefinition,
): Promise<boolean> {
  // 1. 이미 시드됐는지 확인
  try {
    const sources = await client.listSources();
    if (sources.some(s => s.title.startsWith(FOUNDATIONAL_PREFIX))) {
      return false; // 이미 존재
    }
  } catch {
    // listSources 실패 시 시드 시도 (새 노트북일 수 있음)
  }

  // 2. foundational.md 파일 읽기
  const mdPath = path.resolve(agent.knowledgeDir, 'foundational.md');
  if (!existsSync(mdPath)) {
    log('debug', `📓 No foundational knowledge for ${agent.id}: ${mdPath}`);
    return false;
  }

  // 3. NLM source로 추가
  const content = readFileSync(mdPath, 'utf-8');
  const title = `${FOUNDATIONAL_PREFIX} ${agent.name}`;
  await client.addSource(title, content);
  log('info', `📓 Seeded foundational knowledge: ${agent.id}`);
  return true;
}
