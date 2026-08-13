import { createRouter, createWebHistory } from "vue-router";
import DashboardView from "../views/DashboardView.vue";
import JournalView from "../views/JournalView.vue";
import SignalsView from "../views/SignalsView.vue";
import TradeDetailView from "../views/TradeDetailView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "dashboard", component: DashboardView },
    { path: "/signals", name: "signals", component: SignalsView },
    { path: "/signals/:symbol", name: "trade-detail", component: TradeDetailView, props: true },
    { path: "/journal", name: "journal", component: JournalView },
  ],
});

export default router;
