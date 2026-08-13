<script setup lang="ts">
import { createChart, type CandlestickData, type IChartApi, type ISeriesApi, type UTCTimestamp } from "lightweight-charts";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { Bar } from "../types";

const props = defineProps<{ bars: Bar[] }>();

const container = ref<HTMLDivElement | null>(null);
let chart: IChartApi | null = null;
let series: ISeriesApi<"Candlestick"> | null = null;

function toCandlestickData(bars: Bar[]): CandlestickData[] {
  return bars.map((b) => ({
    time: Math.floor(new Date(b.timestamp).getTime() / 1000) as UTCTimestamp,
    open: b.open,
    high: b.high,
    low: b.low,
    close: b.close,
  }));
}

function render() {
  if (!series) return;
  series.setData(toCandlestickData(props.bars));
}

onMounted(() => {
  if (!container.value) return;
  chart = createChart(container.value, {
    height: 320,
    width: container.value.clientWidth,
  });
  series = chart.addCandlestickSeries();
  render();
});

watch(() => props.bars, render);

onBeforeUnmount(() => {
  chart?.remove();
  chart = null;
  series = null;
});
</script>

<template>
  <div ref="container" class="chart"></div>
</template>

<style scoped>
.chart {
  width: 100%;
}
</style>
