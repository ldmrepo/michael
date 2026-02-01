/**
 * Michael Agent Card
 *
 * Defines Michael's A2A capabilities and skills.
 */

import type { AgentCard } from './types.js';

/**
 * Michael's Agent Card
 */
export const MICHAEL_AGENT_CARD: AgentCard = {
  name: 'michael',
  description: '24/7 개인 AI 어시스턴트. 일정 관리, 정보 검색, 예약 등 다양한 작업 수행. 모든 대화를 기억하고 능동적으로 알림을 보냅니다.',
  url: process.env.MICHAEL_URL || 'http://localhost:18789',
  version: '1.0.0',
  protocolVersion: '0.3.0',
  defaultInputModes: ['text'],
  defaultOutputModes: ['text', 'a2ui'],
  capabilities: {
    streaming: true,
    pushNotifications: true,
    a2ui: true,
    multiTurn: true,
    stateful: true,
  },
  skills: [
    {
      id: 'memory-search',
      name: 'Memory Search',
      description: '과거 대화 및 저장된 정보 검색',
      examples: [
        '지난주에 뭐 얘기했지?',
        '내 생일 언제야?',
        '내가 좋아하는 음식 뭐라고 했지?',
      ],
    },
    {
      id: 'schedule-management',
      name: 'Schedule Management',
      description: '일정 등록, 조회, 알림 설정',
      examples: [
        '내일 3시에 회의 알려줘',
        '이번 주 일정 보여줘',
        '매주 월요일 9시에 주간 보고 알림 설정해줘',
      ],
    },
    {
      id: 'proactive-notification',
      name: 'Proactive Notification',
      description: '능동적 알림 및 리마인더',
      examples: [
        '매일 아침 9시에 날씨 알려줘',
        '30분 후에 약 먹으라고 알려줘',
        '회의 10분 전에 미리 알려줘',
      ],
    },
    {
      id: 'fact-storage',
      name: 'Fact Storage',
      description: '중요한 정보 저장 및 조회',
      examples: [
        '내 생일은 3월 15일이야',
        '집 주소는 서울 강남구야',
        '비밀번호 힌트는 "첫 애완동물"이야',
      ],
    },
    {
      id: 'general-conversation',
      name: 'General Conversation',
      description: '일반 대화 및 질문 답변',
      examples: [
        '오늘 기분이 어때?',
        '파이썬으로 웹 크롤러 만드는 법 알려줘',
        '추천할 만한 책 있어?',
      ],
    },
  ],
  securitySchemes: {
    telegramAuth: {
      type: 'custom',
      description: 'Telegram User ID 기반 인증',
    },
    bearerAuth: {
      type: 'bearer',
      description: 'Bearer token 인증',
    },
  },
  provider: {
    name: 'Michael Project',
    url: 'https://github.com/michael-ai',
  },
};

/**
 * Get Michael's agent card with custom URL
 */
export function getMichaelAgentCard(baseUrl?: string): AgentCard {
  return {
    ...MICHAEL_AGENT_CARD,
    url: baseUrl || MICHAEL_AGENT_CARD.url,
  };
}

/**
 * Validate that a request can use a specific skill
 */
export function canUseSkill(skillId: string): boolean {
  return MICHAEL_AGENT_CARD.skills?.some((s) => s.id === skillId) ?? false;
}

/**
 * Get skill by ID
 */
export function getSkill(skillId: string) {
  return MICHAEL_AGENT_CARD.skills?.find((s) => s.id === skillId);
}
