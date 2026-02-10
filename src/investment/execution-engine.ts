/**
 * Execution Engine - proposal lifecycle, callback handling, order execution
 * Semi-auto: analysis → proposal → Telegram approval → execute
 */

import { log } from '../utils/logger.js';
import { PortfolioStore } from './portfolio-store.js';
import { InvestmentScheduler } from './scheduler-jobs.js';
import type { Proposal } from './types.js';

type SendProposalFn = (userId: string, text: string,
                       buttons: Array<{ text: string; data: string }>) => void;
type SendResultFn = (userId: string, text: string) => void;

export class ExecutionEngine {
  private store: PortfolioStore;
  private scheduler: InvestmentScheduler;
  private sendProposal?: SendProposalFn;
  private sendResult?: SendResultFn;
  private proposalExpiryMin: number;

  constructor(store: PortfolioStore, scheduler: InvestmentScheduler) {
    this.store = store;
    this.scheduler = scheduler;
    this.proposalExpiryMin = parseInt(process.env.INVESTMENT_PROPOSAL_EXPIRY_MIN || '30');
  }

  setSendProposal(fn: SendProposalFn): void {
    this.sendProposal = fn;
  }

  setSendResult(fn: SendResultFn): void {
    this.sendResult = fn;
  }

  /**
   * Create a trade proposal and send to Telegram for approval
   */
  createProposal(
    userId: string,
    proposalType: string,
    symbol: string,
    side: 'BUY' | 'SELL',
    accountType: string,
    orderType: string,
    quantity: number,
    price?: number,
    leverage?: number,
    stopLoss?: number,
    takeProfit?: number,
    rationale?: string,
    analysisId?: number,
  ): number {
    const expiresAt = Math.floor(Date.now() / 1000) + this.proposalExpiryMin * 60;

    const proposalId = this.store.insertProposal(
      userId, proposalType, symbol, side, accountType, orderType,
      quantity, price, leverage, stopLoss, takeProfit, rationale,
      analysisId, expiresAt,
    );

    // Format and send to Telegram
    if (this.sendProposal) {
      const text = this.formatProposalMessage(
        proposalId, symbol, side, accountType, orderType,
        quantity, price, stopLoss, takeProfit, rationale,
      );
      const buttons = [
        { text: '✅ 실행', data: `inv_approve:id=${proposalId}` },
        { text: '❌ 거부', data: `inv_reject:id=${proposalId}` },
        { text: '✏️ 수정', data: `inv_modify:id=${proposalId}` },
      ];
      this.sendProposal(userId, text, buttons);
    }

    log('info', `📋 Proposal created: #${proposalId} ${side} ${quantity} ${symbol}`);
    return proposalId;
  }

  /**
   * Format proposal for Telegram
   */
  private formatProposalMessage(
    id: number, symbol: string, side: string, accountType: string,
    _orderType: string, quantity: number, price?: number,
    stopLoss?: number, takeProfit?: number, rationale?: string,
  ): string {
    const estValue = price ? (quantity * price) : 0;
    let msg = `📋 매매 추천 #${id}\n`;
    msg += `${side} ${symbol} (${accountType}) ${quantity}개`;
    if (estValue > 0) msg += ` (~$${estValue.toLocaleString('en-US', { maximumFractionDigits: 0 })})`;
    msg += '\n';

    if (stopLoss || takeProfit) {
      const parts = [];
      if (stopLoss) parts.push(`SL $${stopLoss.toLocaleString()}`);
      if (takeProfit) parts.push(`TP $${takeProfit.toLocaleString()}`);
      msg += parts.join(' | ') + '\n';
    }

    if (rationale) {
      msg += `사유: ${rationale}\n`;
    }

    msg += `⏰ ${this.proposalExpiryMin}분 후 만료`;
    return msg;
  }

  /**
   * Handle Telegram callback for proposal actions
   */
  async handleCallback(action: string, params: Record<string, string>, userId: string): Promise<void> {
    const proposalId = parseInt(params.id || '0');
    if (!proposalId) {
      log('warn', '⚠️ No proposal ID in callback');
      return;
    }

    const proposal = this.store.getProposal(proposalId);
    if (!proposal) {
      log('warn', `⚠️ Proposal ${proposalId} not found`);
      return;
    }

    if (proposal.userId !== userId) {
      log('warn', `⚠️ User mismatch for proposal ${proposalId}`);
      return;
    }

    switch (action) {
      case 'inv_approve':
        await this.approveProposal(proposal);
        break;
      case 'inv_reject':
        this.store.updateProposalStatus(proposalId, 'rejected');
        this.sendResult?.(userId, `❌ 제안 #${proposalId} 거부됨`);
        break;
      default:
        log('warn', `⚠️ Unknown execution action: ${action}`);
    }
  }

  /**
   * Approve and execute a proposal
   */
  private async approveProposal(proposal: Proposal): Promise<void> {
    // Check expiry
    const now = Math.floor(Date.now() / 1000);
    if (proposal.expiresAt && now > proposal.expiresAt) {
      this.store.updateProposalStatus(proposal.id, 'expired');
      this.sendResult?.(proposal.userId, `⏰ 제안 #${proposal.id} 만료됨`);
      return;
    }

    // Update status to approved
    this.store.updateProposalStatus(proposal.id, 'approved');

    // Execute via Python
    const output = await this.scheduler.spawnPython(
      'execute_order.py',
      ['--proposal-id', String(proposal.id)],
      `execute_${proposal.id}`,
    );

    if (output.status === 'success') {
      const data = output.data || {};
      this.sendResult?.(
        proposal.userId,
        `✅ 체결: ${proposal.side} ${data.filled_qty || proposal.quantity} ${proposal.symbol} @ $${data.fill_price || proposal.price || '?'}`,
      );
    } else {
      this.sendResult?.(
        proposal.userId,
        `❌ 주문 실패 #${proposal.id}: ${output.message}`,
      );
    }
  }

  /**
   * Expire old pending proposals
   */
  expireOldProposals(): number {
    return this.store.expirePendingProposals();
  }

  /**
   * Get pending proposals
   */
  getPending(userId: string): Proposal[] {
    return this.store.getPendingProposals(userId);
  }

  /**
   * Get a proposal by ID
   */
  getProposal(id: number): Proposal | null {
    return this.store.getProposal(id);
  }
}
