import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { Gateway, GatewayMessage } from './gateway.js';
import WebSocket from 'ws';

describe('Gateway', () => {
  let gateway: Gateway;
  const testPort = 18790; // 다른 포트 사용

  beforeEach(async () => {
    gateway = new Gateway(testPort);
    await gateway.start();
  });

  afterEach(async () => {
    await gateway.close();
  });

  describe('Connection', () => {
    it('should accept client connections', (done) => {
      const client = new WebSocket(`ws://127.0.0.1:${testPort}`);

      client.on('open', () => {
        expect(client.readyState).toBe(WebSocket.OPEN);
        client.close();
        done();
      });

      client.on('error', (error) => {
        done(error);
      });
    });

    it('should send welcome message on connection', (done) => {
      const client = new WebSocket(`ws://127.0.0.1:${testPort}`);

      client.on('message', (data) => {
        const message: GatewayMessage = JSON.parse(data.toString());
        expect(message.content).toBe('Connected to Michael Gateway');
        expect(message.from).toBe('agent');
        expect(message.metadata).toHaveProperty('clientId');
        client.close();
        done();
      });
    });

    it('should track connected clients', (done) => {
      const client = new WebSocket(`ws://127.0.0.1:${testPort}`);

      client.on('open', () => {
        // 짧은 대기 후 클라이언트 목록 확인
        setTimeout(() => {
          const clients = gateway.getClients();
          expect(clients.length).toBeGreaterThan(0);
          client.close();
          done();
        }, 100);
      });
    });
  });

  describe('Messaging', () => {
    it('should route messages between clients', (done) => {
      const client1 = new WebSocket(`ws://127.0.0.1:${testPort}`);
      const client2 = new WebSocket(`ws://127.0.0.1:${testPort}`);

      let welcomeCount = 0;
      let client1Ready = false;
      let client2Ready = false;

      // Client1을 telegram으로 등록
      client1.on('message', (data) => {
        const message: GatewayMessage = JSON.parse(data.toString());
        
        if (message.content === 'Connected to Michael Gateway') {
          welcomeCount++;
          if (!client1Ready) {
            client1Ready = true;
            // Client1을 telegram으로 등록
            client1.send(JSON.stringify({
              from: 'telegram',
              to: 'agent',
              userId: 'user1',
              content: 'Hello from telegram',
            }));
          }
        }
      });

      // Client2를 agent로 등록하고 메시지 수신 대기
      client2.on('message', (data) => {
        const message: GatewayMessage = JSON.parse(data.toString());
        
        if (message.content === 'Connected to Michael Gateway') {
          welcomeCount++;
          if (!client2Ready) {
            client2Ready = true;
            // Client2를 agent로 등록
            client2.send(JSON.stringify({
              from: 'agent',
              to: 'telegram',
              userId: 'system',
              content: 'test registration',
            }));
          }
        } else if (message.from === 'telegram') {
          // Telegram으로부터 메시지 수신
          expect(message.content).toBe('Hello from telegram');
          expect(message.to).toBe('agent');
          client1.close();
          client2.close();
          done();
        }
      });
    });

    it('should handle invalid JSON messages', (done) => {
      const client = new WebSocket(`ws://127.0.0.1:${testPort}`);
      let receivedWelcome = false;

      client.on('message', (data) => {
        const message: GatewayMessage = JSON.parse(data.toString());
        
        if (!receivedWelcome) {
          receivedWelcome = true;
          // 잘못된 JSON 전송
          client.send('invalid json{');
        } else {
          // 에러 응답 수신
          expect(message.content).toBe('Invalid message format');
          expect(message.metadata).toHaveProperty('error');
          client.close();
          done();
        }
      });
    });
  });

  describe('Client Management', () => {
    it('should remove disconnected clients', (done) => {
      const client = new WebSocket(`ws://127.0.0.1:${testPort}`);

      client.on('open', () => {
        setTimeout(() => {
          const clientsBefore = gateway.getClients();
          expect(clientsBefore.length).toBeGreaterThan(0);

          client.close();

          // 연결 종료 후 클라이언트 목록 확인
          setTimeout(() => {
            const clientsAfter = gateway.getClients();
            expect(clientsAfter.length).toBeLessThan(clientsBefore.length);
            done();
          }, 100);
        }, 100);
      });
    });

    it('should handle multiple simultaneous connections', (done) => {
      const clients: WebSocket[] = [];
      let connectedCount = 0;

      for (let i = 0; i < 5; i++) {
        const client = new WebSocket(`ws://127.0.0.1:${testPort}`);
        clients.push(client);

        client.on('open', () => {
          connectedCount++;
          
          if (connectedCount === 5) {
            // 모든 클라이언트 연결 완료
            setTimeout(() => {
              const gatewayClients = gateway.getClients();
              expect(gatewayClients.length).toBe(5);
              
              // 모든 클라이언트 종료
              clients.forEach(c => c.close());
              done();
            }, 100);
          }
        });
      }
    });
  });

  describe('Broadcast', () => {
    it('should broadcast message to all clients', (done) => {
      const clients: WebSocket[] = [];
      let welcomeCount = 0;
      let broadcastCount = 0;
      const numClients = 3;

      for (let i = 0; i < numClients; i++) {
        const client = new WebSocket(`ws://127.0.0.1:${testPort}`);
        clients.push(client);

        client.on('message', (data) => {
          const message: GatewayMessage = JSON.parse(data.toString());
          
          if (message.content === 'Connected to Michael Gateway') {
            welcomeCount++;
            
            // 마지막 클라이언트가 연결되면 브로드캐스트 테스트
            if (welcomeCount === numClients) {
              setTimeout(() => {
                gateway.broadcast({
                  from: 'agent',
                  to: 'telegram',
                  userId: 'system',
                  content: 'Broadcast test',
                });
              }, 100);
            }
          } else if (message.content === 'Broadcast test') {
            broadcastCount++;
            
            // 모든 클라이언트가 브로드캐스트를 받았는지 확인
            if (broadcastCount === numClients) {
              clients.forEach(c => c.close());
              done();
            }
          }
        });
      }
    });
  });
});
