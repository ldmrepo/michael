import Database from 'better-sqlite3';
import path from 'node:path';
import fs from 'node:fs/promises';
import { log } from '../utils/logger.js';
import { MemoryIndexManager } from '../memory-new/manager.js';
import type { MichaelMemoryConfig } from '../memory-new/config.js';

/**
 * Message 타입 정의
 */
export interface Message {
  id: number;
  userId: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

/**
 * Fact 타입 정의 (중요 정보)
 */
export interface Fact {
  userId: string;
  key: string;
  value: string;
  updatedAt: number;
}

/**
 * Schedule 타입 정의
 */
export interface Schedule {
  id: string;
  userId: string;
  cronExpression: string;
  message: string;
  active: boolean;
  createdAt: number;
}

/**
 * Memory 클래스
 * SQLite 기반 영구 메모리 시스템
 */
export class Memory {
  private db: Database.Database;
  private dbPath: string;
  private indexManager: MemoryIndexManager | null = null;
  private isSyncing: boolean = false;

  constructor(dbPath: string) {
    this.dbPath = dbPath;
    this.db = new Database(dbPath);
    this.db.pragma('journal_mode = WAL'); // Write-Ahead Logging for better performance
    this.initializeTables();
    log('info', `✅ Memory initialized: ${dbPath}`);
  }

  /**
   * Get the underlying database instance
   * Used by InvestmentService for shared DB access
   */
  getDb(): Database.Database {
    return this.db;
  }

  /**
   * 데이터베이스 테이블 초기화
   */
  private initializeTables(): void {
    // Users 테이블
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        telegram_chat_id TEXT UNIQUE,
        created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
      )
    `);

    // Messages 테이블
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
        content TEXT NOT NULL,
        timestamp INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
      )
    `);

    // Facts 테이블
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS facts (
        user_id TEXT NOT NULL,
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
        PRIMARY KEY (user_id, key),
        FOREIGN KEY (user_id) REFERENCES users(id)
      )
    `);

    // Schedules 테이블
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS schedules (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        cron_expression TEXT NOT NULL,
        message TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
      )
    `);

    // FTS5 전문 검색 테이블
    this.db.exec(`
      CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
        content,
        content='messages',
        content_rowid='id'
      )
    `);

    // FTS5 트리거: INSERT
    this.db.exec(`
      CREATE TRIGGER IF NOT EXISTS messages_fts_insert AFTER INSERT ON messages BEGIN
        INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
      END
    `);

    // FTS5 트리거: UPDATE
    this.db.exec(`
      CREATE TRIGGER IF NOT EXISTS messages_fts_update AFTER UPDATE ON messages BEGIN
        UPDATE messages_fts SET content = new.content WHERE rowid = new.id;
      END
    `);

    // FTS5 트리거: DELETE
    this.db.exec(`
      CREATE TRIGGER IF NOT EXISTS messages_fts_delete AFTER DELETE ON messages BEGIN
        DELETE FROM messages_fts WHERE rowid = old.id;
      END
    `);

    log('debug', '✅ Database tables initialized');
  }

  /**
   * 사용자 생성 또는 조회
   */
  async ensureUser(userId: string, telegramChatId?: string): Promise<void> {
    const stmt = this.db.prepare(`
      INSERT OR IGNORE INTO users (id, telegram_chat_id)
      VALUES (?, ?)
    `);
    stmt.run(userId, telegramChatId || null);
  }

  /**
   * 메시지 저장
   */
  async saveMessage(
    userId: string,
    role: 'user' | 'assistant',
    content: string
  ): Promise<void> {
    await this.ensureUser(userId);

    const stmt = this.db.prepare(`
      INSERT INTO messages (user_id, role, content)
      VALUES (?, ?, ?)
    `);
    stmt.run(userId, role, content);

    log('debug', `💾 Message saved: ${userId} (${role})`);
  }

  /**
   * 최근 메시지 조회
   */
  async getRecentMessages(userId: string, limit: number): Promise<Message[]> {
    // Subquery to get recent messages and order them chronologically
    const stmt = this.db.prepare(`
      SELECT sub.id, sub.user_id as userId, sub.role, sub.content, sub.timestamp
      FROM (
        SELECT id, user_id, role, content, timestamp
        FROM messages
        WHERE user_id = ?
        ORDER BY timestamp DESC, id DESC
        LIMIT ?
      ) AS sub
      ORDER BY sub.timestamp ASC, sub.id ASC
    `);

    return stmt.all(userId, limit) as Message[];
  }

  /**
   * 메시지 전문 검색 (FTS5 키워드 검색)
   *
   * 레거시 FTS5 기반 검색입니다. 정확한 키워드 매칭이 필요한 경우 사용하세요.
   * 의미적 검색이 필요한 경우 searchMessagesVector()를 사용하세요.
   */
  async searchMessages(userId: string, query: string): Promise<Message[]> {
    const stmt = this.db.prepare(`
      SELECT m.id, m.user_id as userId, m.role, m.content, m.timestamp
      FROM messages m
      JOIN messages_fts fts ON m.id = fts.rowid
      WHERE m.user_id = ? AND messages_fts MATCH ?
      ORDER BY m.timestamp DESC
      LIMIT 50
    `);

    return stmt.all(userId, query) as Message[];
  }

  /**
   * 벡터 기반 하이브리드 검색 (벡터 + FTS5)
   *
   * Moltbot의 MemoryIndexManager를 사용하여 의미적 유사도 기반 검색을 수행합니다.
   * 벡터 임베딩과 키워드 검색을 조합한 하이브리드 방식입니다.
   *
   * @param userId - 사용자 ID
   * @param query - 검색 쿼리
   * @param options - 검색 옵션
   * @returns 스코어와 함께 반환된 메시지 배열
   *
   * @example
   * ```typescript
   * // "회의 준비"와 의미적으로 유사한 메시지 검색
   * const results = await memory.searchMessagesVector("user123", "회의 준비", {
   *   maxResults: 5,
   *   minScore: 0.7,
   *   hybrid: true
   * });
   *
   * results.forEach(msg => {
   *   console.log(`[Score: ${msg.score.toFixed(2)}] ${msg.content}`);
   * });
   * ```
   */
  async searchMessagesVector(
    userId: string,
    query: string,
    options?: {
      maxResults?: number;
      minScore?: number;
      vectorWeight?: number;
      textWeight?: number;
      hybrid?: boolean;
    }
  ): Promise<Array<Message & { score: number; vectorScore?: number; textScore?: number }>> {
    if (!this.indexManager) {
      throw new Error(
        'Vector search not initialized. Call initializeVectorSearch() first.'
      );
    }

    try {
      // MemoryIndexManager로 검색
      const results = await this.indexManager.search(query, {
        maxResults: options?.maxResults ?? 10,
        minScore: options?.minScore ?? 0.0,
      });

      if (results.length === 0) {
        return [];
      }

      // chunks 결과 → messages 변환
      // path 형식: "{dataDir}/memory/user-{userId}/msg-{messageId}.md"
      const messageResults: Array<Message & { score: number }> = [];

      for (const result of results) {
        // path에서 message id 추출
        // 예: /data/memory/user-user123/msg-5.md
        const match = result.path.match(/user-([^/]+)\/msg-(\d+)\.md$/);
        if (!match) {
          log('warn', `Failed to parse chunk path: ${result.path} (expected format: user-{userId}/msg-{id}.md)`);
          continue;
        }

        const pathUserId = match[1];
        const messageId = parseInt(match[2], 10);

        // 검색한 사용자와 일치하는지 확인 (다른 사용자의 결과는 조용히 스킵)
        if (pathUserId !== userId) continue;

        // messages 테이블에서 원본 조회
        const stmt = this.db.prepare(`
          SELECT id, user_id as userId, role, content, timestamp
          FROM messages
          WHERE user_id = ? AND id = ?
        `);

        const message = stmt.get(userId, messageId) as Message | undefined;
        if (!message) continue;

        messageResults.push({
          ...message,
          score: result.score,
        });
      }

      return messageResults;
    } catch (error) {
      const queryPreview = query.length > 50 ? query.substring(0, 50) + '...' : query;
      log('error', `Vector search failed for user ${userId}, query="${queryPreview}": ${error}`);
      throw error;
    }
  }

  /**
   * Fact 저장
   */
  async saveFact(userId: string, key: string, value: string): Promise<void> {
    await this.ensureUser(userId);

    const stmt = this.db.prepare(`
      INSERT INTO facts (user_id, key, value, updated_at)
      VALUES (?, ?, ?, strftime('%s', 'now'))
      ON CONFLICT(user_id, key) DO UPDATE SET
        value = excluded.value,
        updated_at = excluded.updated_at
    `);
    stmt.run(userId, key, value);

    log('debug', `💾 Fact saved: ${userId}/${key}`);
  }

  /**
   * Fact 조회
   */
  async getFact(userId: string, key: string): Promise<string | null> {
    const stmt = this.db.prepare(`
      SELECT value FROM facts
      WHERE user_id = ? AND key = ?
    `);

    const row = stmt.get(userId, key) as { value: string } | undefined;
    return row?.value || null;
  }

  /**
   * 모든 Fact 조회
   */
  async getAllFacts(userId: string): Promise<Record<string, string>> {
    const stmt = this.db.prepare(`
      SELECT key, value FROM facts
      WHERE user_id = ?
      ORDER BY updated_at DESC
    `);

    const rows = stmt.all(userId) as Array<{ key: string; value: string }>;
    return Object.fromEntries(rows.map((row) => [row.key, row.value]));
  }

  /**
   * Fact 삭제
   */
  async deleteFact(userId: string, key: string): Promise<void> {
    const stmt = this.db.prepare(`
      DELETE FROM facts
      WHERE user_id = ? AND key = ?
    `);
    stmt.run(userId, key);

    log('debug', `🗑️ Fact deleted: ${userId}/${key}`);
  }

  /**
   * 스케줄 저장
   */
  async saveSchedule(
    id: string,
    userId: string,
    cronExpression: string,
    message: string
  ): Promise<void> {
    await this.ensureUser(userId);

    const stmt = this.db.prepare(`
      INSERT INTO schedules (id, user_id, cron_expression, message)
      VALUES (?, ?, ?, ?)
      ON CONFLICT(id) DO UPDATE SET
        cron_expression = excluded.cron_expression,
        message = excluded.message
    `);
    stmt.run(id, userId, cronExpression, message);

    log('debug', `⏰ Schedule saved: ${id}`);
  }

  /**
   * 스케줄 조회
   */
  async getSchedule(id: string): Promise<Schedule | null> {
    const stmt = this.db.prepare(`
      SELECT id, user_id as userId, cron_expression as cronExpression,
             message, active, created_at as createdAt
      FROM schedules
      WHERE id = ?
    `);

    const row = stmt.get(id) as Schedule | undefined;
    if (!row) return null;

    return {
      ...row,
      active: Boolean(row.active), // SQLite INTEGER to boolean
    };
  }

  /**
   * 모든 활성 스케줄 조회
   */
  async getAllSchedules(userId?: string): Promise<Schedule[]> {
    let query = `
      SELECT id, user_id as userId, cron_expression as cronExpression,
             message, active, created_at as createdAt
      FROM schedules
      WHERE active = 1
    `;

    const params: string[] = [];
    if (userId) {
      query += ' AND user_id = ?';
      params.push(userId);
    }

    query += ' ORDER BY created_at DESC';

    const stmt = this.db.prepare(query);
    const rows = stmt.all(...params) as any[];

    return rows.map((row) => ({
      id: row.id,
      userId: row.userId,
      cronExpression: row.cronExpression,
      message: row.message,
      active: Boolean(row.active),
      createdAt: row.createdAt,
    }));
  }

  /**
   * 스케줄 비활성화
   */
  async deactivateSchedule(id: string): Promise<void> {
    const stmt = this.db.prepare(`
      UPDATE schedules SET active = 0
      WHERE id = ?
    `);
    stmt.run(id);

    log('debug', `⏸️ Schedule deactivated: ${id}`);
  }

  /**
   * 스케줄 활성화
   */
  async activateSchedule(id: string): Promise<void> {
    const stmt = this.db.prepare(`
      UPDATE schedules SET active = 1
      WHERE id = ?
    `);
    stmt.run(id);

    log('debug', `▶️ Schedule activated: ${id}`);
  }

  /**
   * 스케줄 삭제
   */
  async deleteSchedule(id: string): Promise<void> {
    const stmt = this.db.prepare(`
      DELETE FROM schedules WHERE id = ?
    `);
    stmt.run(id);

    log('debug', `🗑️ Schedule deleted: ${id}`);
  }

  /**
   * 벡터 검색 엔진 초기화
   *
   * Moltbot의 MemoryIndexManager를 통합하여 벡터 임베딩 기반 검색을 활성화합니다.
   *
   * @param config - Michael 메모리 설정
   */
  async initializeVectorSearch(config: MichaelMemoryConfig): Promise<void> {
    try {
      const dataDir = path.dirname(this.dbPath);

      this.indexManager = await MemoryIndexManager.get({
        cfg: config,
        dataDir,
      });

      if (!this.indexManager) {
        throw new Error('Failed to initialize MemoryIndexManager');
      }

      log('info', '✅ Vector search initialized');
    } catch (error) {
      const dataDir = path.dirname(this.dbPath);
      const provider = config.memory?.search?.provider ?? 'unknown';
      log('error', `❌ Vector search initialization failed (dataDir=${dataDir}, provider=${provider}): ${error}`);
      throw error;
    }
  }

  /**
   * Messages 테이블을 Chunks로 인덱싱
   *
   * messages 테이블의 모든 메시지를 읽어서 사용자별로 메모리 파일로 저장한 후,
   * MemoryIndexManager가 자동으로 임베딩을 생성하고 chunks 테이블에 인덱싱합니다.
   *
   * @param userId - 특정 사용자만 인덱싱 (선택사항)
   */
  async syncMessagesToChunks(userId?: string): Promise<void> {
    if (!this.indexManager) {
      throw new Error(
        'Vector search not initialized. Call initializeVectorSearch() first.'
      );
    }

    // Prevent concurrent sync operations
    if (this.isSyncing) {
      log('debug', 'Sync already in progress, skipping...');
      return;
    }

    this.isSyncing = true;
    try {
      const dataDir = path.dirname(this.dbPath);
      const memoryDir = path.join(dataDir, 'memory');

      // memory 디렉토리 생성
      await fs.mkdir(memoryDir, { recursive: true });

      // 사용자 목록 조회
      let query = 'SELECT DISTINCT user_id FROM messages';
      const params: string[] = [];
      if (userId) {
        query += ' WHERE user_id = ?';
        params.push(userId);
      }

      const stmt = this.db.prepare(query);
      const users = stmt.all(...params) as Array<{ user_id: string }>;

      log('info', `📝 Syncing messages to chunks for ${users.length} user(s)...`);

      // 각 사용자의 메시지를 개별 파일로 저장
      for (const user of users) {
        const messagesStmt = this.db.prepare(`
          SELECT id, role, content, timestamp
          FROM messages
          WHERE user_id = ?
          ORDER BY timestamp ASC, id ASC
        `);

        const messages = messagesStmt.all(user.user_id) as Array<{
          id: number;
          role: string;
          content: string;
          timestamp: number;
        }>;

        if (messages.length === 0) continue;

        // 사용자별 디렉토리 생성
        const userDir = path.join(memoryDir, `user-${user.user_id}`);
        await fs.mkdir(userDir, { recursive: true });

        // 각 메시지를 개별 파일로 저장
        for (const msg of messages) {
          const date = new Date(msg.timestamp * 1000).toISOString();
          const content = [
            `# Message ${msg.id}`,
            '',
            `**User ID**: ${user.user_id}`,
            `**Role**: ${msg.role}`,
            `**Time**: ${date}`,
            '',
            '## Content',
            '',
            msg.content,
          ].join('\n');

          const filePath = path.join(userDir, `msg-${msg.id}.md`);
          await fs.writeFile(filePath, content, 'utf-8');
        }

        log('debug', `📄 Created ${messages.length} message files for user ${user.user_id}`);
      }

      // MemoryIndexManager로 자동 인덱싱
      log('info', '🔄 Indexing memory files with embeddings...');
      await this.indexManager.sync({ force: true });

      const status = await this.indexManager.status();
      log('info', `✅ Sync complete: ${status.chunks} chunks indexed`);
    } catch (error) {
      const scope = userId ? `user=${userId}` : 'all users';
      log('error', `❌ Messages sync failed (${scope}): ${error}`);
      throw error;
    } finally {
      this.isSyncing = false;
    }
  }

  /**
   * 데이터베이스 연결 종료
   */
  async close(): Promise<void> {
    if (this.indexManager) {
      await this.indexManager.close();
      this.indexManager = null;
    }
    this.db.close();
    log('info', '👋 Memory closed');
  }
}
