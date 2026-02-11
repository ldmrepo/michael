/**
 * Entry point for pm2 and other process managers
 * Bypasses the import.meta.url guard in index.ts
 */
import { Michael } from './index.js';
import { log } from './utils/logger.js';

const michael = new Michael();
michael.start().catch((error) => {
  log('error', `❌ Fatal error: ${error}`);
  process.exit(1);
});
