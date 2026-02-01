/**
 * Finance Agent Card
 *
 * A2A protocol agent card definition for the Finance Agent.
 * Defines capabilities, skills, and security schemes.
 */
import { AgentCard, AgentSkill } from '../../a2a/types.js';

/**
 * Finance Agent skills
 */
export const FINANCE_SKILLS: AgentSkill[] = [
  {
    id: 'portfolio-analysis',
    name: '포트폴리오 분석',
    description: '투자 포트폴리오 현황 분석 및 리밸런싱 제안',
    examples: [
      '내 포트폴리오 분석해줘',
      '자산 배분 현황 보여줘',
      '리밸런싱이 필요한지 확인해줘',
      '포트폴리오 수익률 알려줘',
    ],
  },
  {
    id: 'market-research',
    name: '시장 조사',
    description: '주식/암호화폐 시세 조회 및 시장 분석',
    examples: [
      '삼성전자 주가 알려줘',
      '비트코인 시세는?',
      'KOSPI 지수 현황',
      '애플 주식 분석해줘',
    ],
  },
  {
    id: 'expense-tracking',
    name: '지출 추적',
    description: '월별 지출 분석 및 예산 관리',
    examples: [
      '이번 달 지출 분석해줘',
      '카테고리별 소비 현황',
      '예산 대비 지출 얼마야?',
      '저축 목표 달성률',
    ],
  },
];

/**
 * Create Finance Agent Card
 *
 * @param baseUrl - Base URL where the agent is hosted
 * @returns A2A AgentCard for Finance Agent
 */
export function createFinanceAgentCard(baseUrl: string): AgentCard {
  return {
    name: 'finance',
    description: '개인 재무 분석 및 투자 조언 AI 에이전트',
    url: baseUrl,
    version: '1.0.0',
    protocolVersion: '0.3.0',
    defaultInputModes: ['text'],
    defaultOutputModes: ['text', 'a2ui'],
    capabilities: {
      streaming: true,
      pushNotifications: false,
      a2ui: true,
      multiTurn: true,
      stateful: false,
    },
    skills: FINANCE_SKILLS,
    securitySchemes: {
      bearerAuth: {
        type: 'bearer',
        description: 'Bearer token authentication',
      },
    },
  };
}

/**
 * Check if a message matches a specific skill
 *
 * @param message - User message text
 * @param skillId - Skill ID to check
 * @returns True if message matches the skill
 */
export function matchesSkill(message: string, skillId: string): boolean {
  const skill = FINANCE_SKILLS.find((s) => s.id === skillId);
  if (!skill || !skill.examples) return false;

  const lowerMessage = message.toLowerCase();

  // Check for keyword matches from examples
  const keywords = extractKeywords(skill.examples);
  return keywords.some((keyword) => lowerMessage.includes(keyword));
}

/**
 * Extract keywords from skill examples
 */
function extractKeywords(examples: string[]): string[] {
  const keywords: string[] = [];

  for (const example of examples) {
    // Extract Korean and English words
    const words = example.toLowerCase().split(/\s+/);
    for (const word of words) {
      // Filter out short/common words
      if (word.length >= 2 && !['내', '해줘', '알려줘', '은?', '는?'].includes(word)) {
        keywords.push(word);
      }
    }
  }

  return [...new Set(keywords)];
}

/**
 * Detect which skill best matches the user's message
 *
 * @param message - User message text
 * @returns Best matching skill ID or null
 */
export function detectSkill(message: string): string | null {
  const lowerMessage = message.toLowerCase();

  // Portfolio keywords
  if (
    lowerMessage.includes('포트폴리오') ||
    lowerMessage.includes('자산') ||
    lowerMessage.includes('배분') ||
    lowerMessage.includes('리밸런싱') ||
    lowerMessage.includes('portfolio')
  ) {
    return 'portfolio-analysis';
  }

  // Market research keywords
  if (
    lowerMessage.includes('주가') ||
    lowerMessage.includes('시세') ||
    lowerMessage.includes('주식') ||
    lowerMessage.includes('비트코인') ||
    lowerMessage.includes('코인') ||
    lowerMessage.includes('지수') ||
    lowerMessage.includes('stock') ||
    lowerMessage.includes('crypto')
  ) {
    return 'market-research';
  }

  // Expense tracking keywords
  if (
    lowerMessage.includes('지출') ||
    lowerMessage.includes('소비') ||
    lowerMessage.includes('예산') ||
    lowerMessage.includes('저축') ||
    lowerMessage.includes('카테고리') ||
    lowerMessage.includes('expense') ||
    lowerMessage.includes('budget')
  ) {
    return 'expense-tracking';
  }

  return null;
}
