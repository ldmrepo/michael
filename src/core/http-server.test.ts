/**
 * HTTP Server Tests
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import request from 'supertest';
import { HttpServer } from './http-server.js';

describe('HttpServer', () => {
  let server: HttpServer;

  beforeEach(() => {
    // Random port for test isolation
    const port = 30000 + Math.floor(Math.random() * 10000);
    server = new HttpServer({
      port,
      webappPath: './test-webapp', // Non-existent path for testing
    });
  });

  afterEach(async () => {
    await server.stop();
  });

  describe('Health Check', () => {
    it('should return ok status', async () => {
      const app = server.getApp();
      const res = await request(app).get('/health');

      expect(res.status).toBe(200);
      expect(res.body.status).toBe('ok');
      expect(res.body.timestamp).toBeDefined();
      expect(res.body.uptime).toBeGreaterThanOrEqual(0);
    });
  });

  describe('Agent Card', () => {
    it('should return Michael agent card', async () => {
      const app = server.getApp();
      const res = await request(app).get('/.well-known/agent.json');

      expect(res.status).toBe(200);
      expect(res.body.name).toBe('michael');
      expect(res.body.skills).toBeDefined();
      expect(Array.isArray(res.body.skills)).toBe(true);
    });
  });

  describe('Session API', () => {
    it('should return 404 for non-existent session', async () => {
      const app = server.getApp();
      const res = await request(app).get('/api/webapp/session/nonexistent');

      expect(res.status).toBe(404);
      expect(res.body.error).toBe('Session not found');
    });

    it('should get session after creation', async () => {
      const webAppManager = server.getWebAppManager();
      const session = webAppManager.createSession(
        'user_123',
        12345,
        { type: 'surface', components: [] },
        { field1: 'value1' }
      );

      const app = server.getApp();
      const res = await request(app).get(`/api/webapp/session/${session.sessionId}`);

      expect(res.status).toBe(200);
      expect(res.body.sessionId).toBe(session.sessionId);
      expect(res.body.dataModel.field1).toBe('value1');
    });

    it('should update session data model', async () => {
      const webAppManager = server.getWebAppManager();
      const session = webAppManager.createSession(
        'user_123',
        12345,
        { type: 'surface', components: [] },
        { field1: 'value1' }
      );

      const app = server.getApp();
      const res = await request(app)
        .post(`/api/webapp/session/${session.sessionId}`)
        .send({ data: { field2: 'value2' } });

      expect(res.status).toBe(200);
      expect(res.body.dataModel.field1).toBe('value1');
      expect(res.body.dataModel.field2).toBe('value2');
    });

    it('should return 404 when updating non-existent session', async () => {
      const app = server.getApp();
      const res = await request(app)
        .post('/api/webapp/session/nonexistent')
        .send({ data: { field: 'value' } });

      expect(res.status).toBe(404);
      expect(res.body.error).toBe('Session not found');
    });
  });

  describe('Message API', () => {
    it('should handle init message for valid session', async () => {
      const webAppManager = server.getWebAppManager();
      const session = webAppManager.createSession(
        'user_123',
        12345,
        { type: 'surface', components: [{ type: 'text', value: 'Hello' }] },
        { name: 'Test' }
      );

      const app = server.getApp();
      const res = await request(app)
        .post('/api/webapp/message')
        .send({ type: 'init', sessionId: session.sessionId });

      expect(res.status).toBe(200);
      expect(res.body.type).toBe('surface');
      expect(res.body.surface.components).toHaveLength(1);
      expect(res.body.data.name).toBe('Test');
    });

    it('should return error for init with invalid session', async () => {
      const app = server.getApp();
      const res = await request(app)
        .post('/api/webapp/message')
        .send({ type: 'init', sessionId: 'invalid' });

      expect(res.status).toBe(200);
      expect(res.body.type).toBe('error');
      expect(res.body.error).toBe('Session not found');
    });

    it('should handle close message', async () => {
      const webAppManager = server.getWebAppManager();
      const session = webAppManager.createSession(
        'user_123',
        12345,
        { type: 'surface', components: [] },
        {}
      );

      const app = server.getApp();
      const res = await request(app)
        .post('/api/webapp/message')
        .send({ type: 'close', sessionId: session.sessionId });

      expect(res.status).toBe(200);
      expect(res.body.type).toBe('close');

      // Session should be deleted
      expect(webAppManager.getSession(session.sessionId)).toBeUndefined();
    });
  });

  describe('Static Files', () => {
    it('should return error for non-existent webapp files', async () => {
      const app = server.getApp();
      const res = await request(app).get('/webapp/nonexistent.js');

      // Express static middleware may return 404 or 500 depending on setup
      expect([404, 500]).toContain(res.status);
    });
  });

  describe('CORS', () => {
    it('should include CORS headers', async () => {
      const app = server.getApp();
      const res = await request(app).get('/health');

      expect(res.headers['access-control-allow-origin']).toBe('*');
    });

    it('should handle OPTIONS request', async () => {
      const app = server.getApp();
      const res = await request(app).options('/api/webapp/session/test');

      expect(res.status).toBe(200);
    });
  });

  describe('Server Lifecycle', () => {
    it('should start and stop without error', async () => {
      const port = 30000 + Math.floor(Math.random() * 10000);
      const testServer = new HttpServer({ port });

      await testServer.start();
      expect(testServer.getPort()).toBe(port);

      await testServer.stop();
    });
  });
});
