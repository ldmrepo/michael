/**
 * Standalone script to seed foundational knowledge into NLM notebooks
 * Usage: npx tsx scripts/seed-knowledge.ts
 */

import { KnowledgeManager } from '../src/knowledge/knowledge-manager.js';
import { seedFoundationalKnowledge, FOUNDATIONAL_PREFIX } from '../src/knowledge/init-agent-knowledge.js';
import type { AgentDefinition } from '../src/knowledge/init-agent-knowledge.js';

async function main() {
  const km = new KnowledgeManager('./data');

  const michaelAgent: AgentDefinition = {
    id: 'michael',
    name: 'Michael',
    team: 'execution',
    role: '24시간 AI 자산관리 전문가',
    instructions: '',
    tools: [],
    knowledgeDir: 'knowledge/michael/',
  };

  console.log('\n📓 Seeding foundational knowledge for michael...\n');

  try {
    const client = await km.getClient(michaelAgent.id);
    const result = await seedFoundationalKnowledge(client, michaelAgent);
    if (result) {
      console.log('  ✅ michael — seeded');
    } else {
      console.log('  ⏭️  michael — skipped (already exists or no file)');
    }
  } catch (e) {
    console.error(`  ❌ michael — failed: ${e}`);
  }

  console.log('\n📊 Done\n');
}

main().catch(console.error);
