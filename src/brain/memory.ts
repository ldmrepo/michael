import Database from 'better-sqlite3';
import { log } from '../utils/logger.js';

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

  constructor(dbPath: string) {
    this.db = new Database(dbPath);
    this.db.pragma('journal_mode = WAL'); // Write-Ahead Logging for better performance
    this.initializeTables();
    log('info', `✅ Memory initialized: ${dbPath}`);
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
   * 메시지 전문 검색 (FTS5)
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
   * 데이터베이스 연결 종료
   */
  close(): void {
    this.db.close();
    log('info', '👋 Memory closed');
  }
}
