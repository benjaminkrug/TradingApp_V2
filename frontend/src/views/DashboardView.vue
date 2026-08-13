<script setup lang="ts">
import { onMounted, ref } from "vue";
import { fetchDashboard } from "../api/client";
import type { DashboardSummary } from "../types";

const summary = ref<DashboardSummary | null>(null);
const error = ref<string | null>(null);
const loading = ref(true);

onMounted(async () => {
  try {
    summary.value = await fetchDashboard();
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <section>
    <h2>Market Overview</h2>
    <p v-if="loading">Loading…</p>
    <p v-else-if="error" class="error">Could not reach the backend API: {{ error }}</p>
    <div v-else-if="summary" class="cards">
      <div class="card"><strong>{{ summary.universe_size }}</strong><span>Universe size</span></div>
      <div class="card"><strong>{{ summary.strategy_count }}</strong><span>Strategies implemented</span></div>
      <div class="card"><strong>{{ summary.validated_strategy_count }}</strong><span>Passed full gate</span></div>
      <div class="card"><strong>{{ summary.signal_count }}</strong><span>Current BUY signals (demo scan)</span></div>
    </div>
    <ul v-if="summary" class="notes">
      <li v-for="note in summary.notes" :key="note">{{ note }}</li>
    </ul>
  </section>
</template>

<style scoped>
.cards {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  margin: 1rem 0;
}
.card {
  border: 1px solid #ddd;
  border-radius: 6px;
  padding: 1rem;
  min-width: 140px;
  text-align: center;
  background: #fff;
}
.card strong {
  display: block;
  font-size: 1.6rem;
}
.card span {
  color: #666;
  font-size: 0.85rem;
}
.notes {
  color: #555;
  font-size: 0.9rem;
}
.error {
  color: #b00020;
}
</style>
