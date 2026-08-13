// Mirrors backend/app/api/schemas.py — keep in sync by hand (small enough
// surface that generating an OpenAPI client would be overkill for now).

export interface StrategyInfo {
  name: string;
  description: string;
  validated: boolean;
  gate_note: string;
}

export interface Signal {
  symbol: string;
  strategy_name: string;
  entry: number;
  stop: number;
  target: number;
  risk_reward: number;
  shares: number;
  score: number | null;
  confidence: string;
  relative_volume: number | null;
  rationale: string[];
  data_source: string;
  account_equity: number;
  risk_pct: number;
}

export interface DashboardSummary {
  universe_size: number;
  strategy_count: number;
  validated_strategy_count: number;
  signal_count: number;
  data_source: string;
  notes: string[];
}

export interface TradeJournalEntry {
  id: string;
  symbol: string;
  opened_at: string;
  closed_at: string | null;
  pnl: number | null;
}

export interface TradeJournal {
  entries: TradeJournalEntry[];
  note: string;
}

export interface Bar {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}
