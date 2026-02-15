/**
 * Standalone script to seed foundational knowledge into NLM notebooks
 * Usage: npx tsx scripts/seed-knowledge.ts
 */

import { KnowledgeManager } from '../src/knowledge/knowledge-manager.js';
import { seedFoundationalKnowledge, FOUNDATIONAL_PREFIX } from '../src/knowledge/init-agent-knowledge.js';
import { getExecutableAgents } from '../src/decision/agent-registry.js';

async function main() {
  const km = new KnowledgeManager('./data');
  const agents = getExecutableAgents();

  console.log(`\n📓 Seeding foundational knowledge for ${agents.length} agents...\n`);

  let seeded = 0;
  let skipped = 0;
  let failed = 0;

  for (const agent of agents) {
    try {
      const client = await km.getClient(agent.id);
      const result = await seedFoundationalKnowledge(client, agent);
      if (result) {
        console.log(`  ✅ ${agent.id} — seeded`);
        seeded++;
      } else {
        console.log(`  ⏭️  ${agent.id} — skipped (already exists or no file)`);
        skipped++;
      }
    } catch (e) {
      console.error(`  ❌ ${agent.id} — failed: ${e}`);
      failed++;
    }
  }

  console.log(`\n📊 Results: ${seeded} seeded, ${skipped} skipped, ${failed} failed\n`);
}

main().catch(console.error);
