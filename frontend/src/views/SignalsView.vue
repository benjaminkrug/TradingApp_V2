<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { fetchSignals, fetchStrategies } from "../api/client";
import type { Signal, StrategyInfo } from "../types";

const strategies = ref<StrategyInfo[]>([]);
const selectedStrategy = ref("vwap_momentum");
const signals = ref<Signal[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

async function load() {
  loading.value = true;
  error.value = null;
  try {
    signals.value = await fetchSignals(selectedStrategy.value);
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  try {
    strategies.value = await fetchStrategies();
  } catch {
    // Strategy picker is a nice-to-have; load() below reports its own errors.
  }
  await load();
});

watch(selectedStrategy, load);
</script>

<template>
  <section>
    <h2>Signals</h2>
    <label>
      Strategy:
      <select v-model="selectedStrategy">
        <option v-for="s in strategies" :key="s.name" :value="s.name">
          {{ s.name }}{{ s.validated ? "" : " (not validated)" }}
        </option>
        <option v-if="!strategies.length" value="vwap_momentum">vwap_momentum</option>
      </select>
    </label>
    <p v-if="loading">Loading…</p>
    <p v-else-if="error" class="error">Could not reach the backend API: {{ error }}</p>
    <p v-else-if="!signals.length">No current BUY signals for this strategy in the demo scan.</p>
    <table v-else>
      <thead>
        <tr>
          <th>Symbol</th>
          <th>Entry</th>
          <th>Stop</th>
          <th>Target</th>
          <th>R:R</th>
          <th>Confidence</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="sig in signals" :key="sig.symbol">
          <td>{{ sig.symbol }}</td>
          <td>{{ sig.entry.toFixed(2) }}</td>
          <td>{{ sig.stop.toFixed(2) }}</td>
          <td>{{ sig.target.toFixed(2) }}</td>
          <td>{{ sig.risk_reward.toFixed(2) }}</td>
          <td>{{ sig.confidence }}</td>
          <td>
            <RouterLink
              :to="{ name: 'trade-detail', params: { symbol: sig.symbol }, query: { strategy: selectedStrategy } }"
            >
              Details
            </RouterLink>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<style scoped>
table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 1rem;
  background: #fff;
}
th,
td {
  text-align: left;
  padding: 0.4rem 0.6rem;
  border-bottom: 1px solid #eee;
}
.error {
  color: #b00020;
}
</style>
