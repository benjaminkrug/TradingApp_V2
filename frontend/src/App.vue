<script setup lang="ts"></script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <h1>TradingApp — Research Dashboard</h1>
      <nav>
        <RouterLink to="/">Dashboard</RouterLink>
        <RouterLink to="/signals">Signals</RouterLink>
        <RouterLink to="/journal">Journal</RouterLink>
      </nav>
    </header>
    <p class="disclaimer">
      Research &amp; paper-trading tool only — not investment advice and not a live/automated
      trading system (see DISCLAIMER.md). Signals and charts shown here are computed against
      synthetic demo data, not real market data, until a verified provider is connected
      (PHASE3_NOTES.md).
    </p>
    <main>
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  max-width: 960px;
  margin: 0 auto;
  padding: 1rem;
  font-family: system-ui, sans-serif;
}
.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}
.app-header nav a {
  margin-left: 1rem;
  font-weight: 600;
}
.disclaimer {
  background: #fff3cd;
  border: 1px solid #ffe69c;
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  font-size: 0.9rem;
}
</style>
