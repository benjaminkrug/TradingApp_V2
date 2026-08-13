// Thin fetch wrapper around backend/app/api/ — no axios dependency needed
// for a handful of GET endpoints.

import type { Bar, DashboardSummary, Signal, StrategyInfo, TradeJournal } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`);
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`${resp.status} ${resp.statusText}: ${body}`);
  }
  return (await resp.json()) as T;
}

export function fetchStrategies(): Promise<StrategyInfo[]> {
  return getJson<StrategyInfo[]>("/api/strategies");
}

export function fetchDashboard(strategy = "vwap_momentum"): Promise<DashboardSummary> {
  return getJson<DashboardSummary>(`/api/dashboard?strategy=${encodeURIComponent(strategy)}`);
}

export function fetchSignals(strategy = "vwap_momentum", limit = 10): Promise<Signal[]> {
  return getJson<Signal[]>(`/api/signals?strategy=${encodeURIComponent(strategy)}&limit=${limit}`);
}

export function fetchSignalDetail(symbol: string, strategy = "vwap_momentum"): Promise<Signal> {
  return getJson<Signal>(`/api/signals/${encodeURIComponent(symbol)}?strategy=${encodeURIComponent(strategy)}`);
}

export function fetchBars(symbol: string, numTradingDays = 10): Promise<Bar[]> {
  return getJson<Bar[]>(`/api/signals/${encodeURIComponent(symbol)}/bars?num_trading_days=${numTradingDays}`);
}

export function fetchTradeJournal(): Promise<TradeJournal> {
  return getJson<TradeJournal>("/api/trades");
}
