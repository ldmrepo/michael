/**
 * KnowledgeManager — 에이전트별 NLM 노트북 관리
 *
 * 각 에이전트는 독립적인 NotebookLM 노트북을 가진다.
 * - 처음 요청 시 `nlm notebook create "Michael: {agent}"` 자동 생성
 * - 매핑을 `data/nlm-notebooks.json`에 영속 저장
 * - `getClient(agentName)`으로 에이전트별 NlmClient 반환
 *
 * CONCEPT.md: "에이전트별 독립 Notebook ID로 지식 격리"
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { NlmClient } from './nlm-client.js';
import type { NotebookOutline } from './nlm-client.js';
import { log } from '../utils/logger.js';

interface NotebookRegistry {
  [agentName: string]: {
    notebookId: string;
    title: string;
    createdAt: string;
  };
}

export class KnowledgeManager {
  private registry: NotebookRegistry = {};
  private clients: Map<string, NlmClient> = new Map();
  private outlineCache: Map<string, { data: NotebookOutline; at: number }> = new Map();
  private readonly OUTLINE_TTL = 60 * 60 * 1000; // 1시간
  private registryPath: string;

  constructor(dataDir: string = './data') {
    this.registryPath = join(dataDir, 'nlm-notebooks.json');
    this.loadRegistry();
  }

  /**
   * 에이전트용 NlmClient 반환 (없으면 노트북 자동 생성)
   */
  async getClient(agentName: string): Promise<NlmClient> {
    // 캐시된 클라이언트 있으면 반환
    const cached = this.clients.get(agentName);
    if (cached) return cached;

    // 레지스트리에 있으면 클라이언트 생성
    const entry = this.registry[agentName];
    if (entry) {
      const client = new NlmClient(entry.notebookId);
      this.clients.set(agentName, client);
      return client;
    }

    // 없으면 노트북 새로 생성
    const title = `Michael: ${agentName}`;
    log('info', `📓 Creating NLM notebook: ${title}`);
    const notebookId = await NlmClient.createNotebook(title);

    this.registry[agentName] = {
      notebookId,
      title,
      createdAt: new Date().toISOString(),
    };
    this.saveRegistry();

    const client = new NlmClient(notebookId);
    this.clients.set(agentName, client);
    log('info', `📓 NLM notebook created: ${title} (${notebookId})`);
    return client;
  }

  /**
   * 에이전트 노트북 ID 조회 (없으면 null)
   */
  getNotebookId(agentName: string): string | null {
    return this.registry[agentName]?.notebookId || null;
  }

  /**
   * 등록된 모든 에이전트 목록
   */
  listAgents(): Array<{ name: string; notebookId: string; title: string }> {
    return Object.entries(this.registry).map(([name, entry]) => ({
      name,
      notebookId: entry.notebookId,
      title: entry.title,
    }));
  }

  /**
   * 기존 노트북 ID를 수동 등록 (이미 생성된 노트북 연결)
   */
  registerNotebook(agentName: string, notebookId: string): void {
    this.registry[agentName] = {
      notebookId,
      title: `Michael: ${agentName}`,
      createdAt: new Date().toISOString(),
    };
    this.saveRegistry();
    this.clients.delete(agentName); // 캐시 무효화
    log('info', `📓 Registered notebook for ${agentName}: ${notebookId}`);
  }

  /**
   * 에이전트 노트북 아웃라인 반환 (1시간 캐시)
   */
  async getOutline(agentName: string): Promise<NotebookOutline | null> {
    const cached = this.outlineCache.get(agentName);
    if (cached && Date.now() - cached.at < this.OUTLINE_TTL) return cached.data;

    try {
      const client = await this.getClient(agentName);
      const outline = await client.describeNotebook();
      this.outlineCache.set(agentName, { data: outline, at: Date.now() });
      return outline;
    } catch {
      return cached?.data || null; // stale > nothing
    }
  }

  /**
   * 아웃라인 캐시 무효화 (Note 추가/변경 후 호출)
   */
  invalidateOutline(agentName: string): void {
    this.outlineCache.delete(agentName);
  }

  // ─── Persistence ────────────────────────────────────

  private loadRegistry(): void {
    if (!existsSync(this.registryPath)) {
      this.registry = {};
      return;
    }
    try {
      const content = readFileSync(this.registryPath, 'utf-8');
      this.registry = JSON.parse(content);
    } catch {
      log('warn', '⚠️ Failed to load nlm-notebooks.json, starting fresh');
      this.registry = {};
    }
  }

  private saveRegistry(): void {
    try {
      const dir = dirname(this.registryPath);
      if (!existsSync(dir)) {
        mkdirSync(dir, { recursive: true });
      }
      writeFileSync(
        this.registryPath,
        JSON.stringify(this.registry, null, 2),
        'utf-8',
      );
    } catch (error) {
      log('error', `❌ Failed to save nlm-notebooks.json: ${error}`);
    }
  }
}
