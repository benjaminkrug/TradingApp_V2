<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { fetchBars, fetchSignalDetail } from "../api/client";
import PriceChart from "../components/PriceChart.vue";
import type { Bar, Signal } from "../types";

const route = useRoute();
const signal = ref<Signal | null>(null);
const bars = ref<Bar[]>([]);
const error = ref<string | null>(null);
const loading = ref(true);

async function load() {
  loading.value = true;
  error.value = null;
  signal.value = null;
  const symbol = String(route.params.symbol);
  const strategy = typeof route.query.strategy === "string" ? route.query.strategy : "vwap_momentum";
  try {
    const [sig, barData] = await Promise.all([fetchSignalDetail(symbol, strategy), fetchBars(symbol)]);
    signal.value = sig;
    bars.value = barData;
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    loading.value = false;
  }
}

onMounted(load);
watch(() => [route.params.symbol, route.query.strategy], load);
</script>

<template>
  <section>
    <RouterLink to="/signals">&larr; Back to signals</RouterLink>
    <h2>Trade Detail — {{ route.params.symbol }}</h2>
    <p v-if="loading">Loading…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <div v-else-if="signal">
      <PriceChart :bars="bars" />
      <dl>
        <dt>Strategy</dt>
        <dd>{{ signal.strategy_name }}</dd>
        <dt>Entry</dt>
        <dd>{{ signal.entry.toFixed(2) }}</dd>
        <dt>Stop</dt>
        <dd>{{ signal.stop.toFixed(2) }}</dd>
        <dt>Target</dt>
        <dd>{{ signal.target.toFixed(2) }}</dd>
        <dt>Risk:Reward</dt>
        <dd>{{ signal.risk_reward.toFixed(2) }}</dd>
        <dt>Shares (demo sizing)</dt>
        <dd>{{ signal.shares.toFixed(2) }}</dd>
        <dt>Confidence</dt>
        <dd>{{ signal.confidence }}</dd>
        <dt>Relative volume</dt>
        <dd>{{ signal.relative_volume?.toFixed(2) ?? "n/a" }}</dd>
      </dl>
      <h3>Rationale</h3>
      <ul>
        <li v-for="line in signal.rationale" :key="line">{{ line }}</li>
      </ul>
      <p class="notice">
        Data source: {{ signal.data_source }} — account equity ${{ signal.account_equity.toLocaleString() }}, risk
        {{ (signal.risk_pct * 100).toFixed(2) }}% per trade (demo defaults, not confirmed values — see
        DECISIONS.md).
      </p>
    </div>
  </section>
</template>

<style scoped>
dl {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 0.25rem 1rem;
  margin-top: 1rem;
}
.error {
  color: #b00020;
}
.notice {
  color: #666;
  font-size: 0.85rem;
}
</style>
