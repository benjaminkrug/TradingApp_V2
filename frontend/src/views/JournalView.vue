<script setup lang="ts">
import { onMounted, ref } from "vue";
import { fetchTradeJournal } from "../api/client";
import type { TradeJournal } from "../types";

const journal = ref<TradeJournal | null>(null);
const error = ref<string | null>(null);
const loading = ref(true);

onMounted(async () => {
  try {
    journal.value = await fetchTradeJournal();
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <section>
    <h2>Trade Journal</h2>
    <p v-if="loading">Loading…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <template v-else-if="journal">
      <p class="notice">{{ journal.note }}</p>
      <table v-if="journal.entries.length">
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Opened</th>
            <th>Closed</th>
            <th>PnL</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="e in journal.entries" :key="e.id">
            <td>{{ e.symbol }}</td>
            <td>{{ e.opened_at }}</td>
            <td>{{ e.closed_at ?? "—" }}</td>
            <td>{{ e.pnl ?? "—" }}</td>
          </tr>
        </tbody>
      </table>
    </template>
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
.notice {
  color: #666;
}
</style>
