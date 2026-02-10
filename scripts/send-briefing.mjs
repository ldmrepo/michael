/**
 * One-shot script: generate daily briefing and send to Telegram
 */
import Database from 'better-sqlite3';
import { PortfolioStore } from '../dist/investment/portfolio-store.js';
import { InvestmentScheduler } from '../dist/investment/scheduler-jobs.js';
import { AnalysisEngine } from '../dist/investment/analysis-engine.js';
import { Telegraf } from 'telegraf';
import dotenv from 'dotenv';
dotenv.config();

const db = new Database('data/memory.db');
const store = new PortfolioStore(db);
const scheduler = new InvestmentScheduler('default');
const engine = new AnalysisEngine(store, scheduler);

// Find Telegram chat ID (user_id IS the chat ID for Telegram users)
const user = db.prepare("SELECT id FROM users WHERE id GLOB '[0-9]*' LIMIT 1").get();
const chatId = user?.id;
console.log('Chat ID:', chatId);

if (!chatId) {
  console.log('No chat ID found. Send a message to the bot first.');
  process.exit(1);
}

// Generate report
let reportText = '';
let analysisId = 0;
engine.setSendReport((userId, text, buttons) => {
  reportText = text;
  const idMatch = buttons?.[0]?.data?.match(/id=(\d+)/);
  if (idMatch) analysisId = parseInt(idMatch[1]);
});
await engine.runAnalysis('default', 'daily');

if (!reportText) {
  console.log('No report generated');
  process.exit(1);
}

// Send to Telegram
const bot = new Telegraf(process.env.TELEGRAM_BOT_TOKEN);
const keyboard = {
  inline_keyboard: [[
    { text: '📋 상세', callback_data: `inv_analysis_detail:id=${analysisId}` },
    { text: '💰 포트폴리오', callback_data: 'inv_portfolio' },
    { text: '🔔 알림설정', callback_data: 'inv_risk_settings' },
  ]]
};

try {
  await bot.telegram.sendMessage(chatId, reportText, { reply_markup: keyboard });
  console.log('✅ Telegram 전송 성공!');
} catch (err) {
  console.log('❌ Telegram error:', err.message);
}

db.close();
