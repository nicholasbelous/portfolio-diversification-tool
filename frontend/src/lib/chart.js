export const CHART_RANGES = [
  { key: "3M", days: 63, label: "3 Months" },
  { key: "6M", days: 126, label: "6 Months" },
  { key: "1Y", days: 252, label: "1 Year" },
  { key: "MAX", days: null, label: "Max" }
];

const CHART_LINE_COLORS = {
  current: "#e76f51",
  optimized: "#2a9d8f",
  benchmark: "#3f6ee8"
};

function toFinite(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function trimSeries(points, days) {
  if (!Array.isArray(points)) {
    return [];
  }
  const cleaned = points
    .map((point) => ({
      date: point?.date,
      value: toFinite(point?.value)
    }))
    .filter((point) => point.date && point.value != null);

  if (days == null || cleaned.length <= days) {
    return cleaned;
  }
  return cleaned.slice(cleaned.length - days);
}

function createLine(points, key, label, getX, getY) {
  const polyline = points
    .map((point, index) => `${getX(index, points.length).toFixed(2)},${getY(point.value).toFixed(2)}`)
    .join(" ");

  return {
    key,
    label,
    color: CHART_LINE_COLORS[key] || "#2a9d8f",
    points,
    polyline,
    lastValue: points.length ? points[points.length - 1].value : null
  };
}

export function buildComparisonChart(historyCompare, rangeKey) {
  if (!historyCompare?.series) {
    return null;
  }

  const range = CHART_RANGES.find((entry) => entry.key === rangeKey) ?? CHART_RANGES[2];
  const current = trimSeries(historyCompare.series.current, range.days);
  const optimized = trimSeries(historyCompare.series.optimized, range.days);
  const benchmark = trimSeries(historyCompare.series.benchmark, range.days);

  const series = [
    { key: "current", label: "Current Portfolio", points: current },
    { key: "optimized", label: "Optimized Portfolio", points: optimized },
    { key: "benchmark", label: "SPY Benchmark", points: benchmark }
  ].filter((entry) => entry.points.length > 1);

  if (!series.length) {
    return null;
  }

  const values = series.flatMap((entry) => entry.points.map((point) => point.value)).filter((value) => value != null);
  if (!values.length) {
    return null;
  }

  let yMin = Math.min(...values);
  let yMax = Math.max(...values);
  if (Math.abs(yMax - yMin) < 1e-9) {
    yMin = yMin * 0.99;
    yMax = yMax * 1.01;
  }

  const width = 980;
  const height = 420;
  const padding = { top: 24, right: 18, bottom: 42, left: 58 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;

  function getX(index, length) {
    if (length <= 1) {
      return padding.left;
    }
    return padding.left + (index / (length - 1)) * plotWidth;
  }

  function getY(value) {
    const ratio = (value - yMin) / (yMax - yMin);
    return padding.top + plotHeight * (1 - ratio);
  }

  const lines = series.map((entry) => createLine(entry.points, entry.key, entry.label, getX, getY));

  const yTicks = Array.from({ length: 5 }).map((_, index) => {
    const ratio = index / 4;
    const value = yMax - ratio * (yMax - yMin);
    return {
      value,
      y: getY(value),
      label: `${((value - 1) * 100).toFixed(1)}%`
    };
  });

  const referenceLine = lines.reduce((best, candidate) => {
    if (!best || candidate.points.length > best.points.length) {
      return candidate;
    }
    return best;
  }, null);

  const referencePoints = referenceLine?.points || [];
  const xTicks = [];
  if (referencePoints.length) {
    const midIndex = Math.floor((referencePoints.length - 1) / 2);
    const indices = Array.from(new Set([0, midIndex, referencePoints.length - 1]));
    indices.forEach((index) => {
      xTicks.push({
        x: getX(index, referencePoints.length),
        label: referencePoints[index]?.date || ""
      });
    });
  }

  return {
    width,
    height,
    padding,
    lines,
    yTicks,
    xTicks,
    startDate: referencePoints[0]?.date || historyCompare.start_date,
    endDate: referencePoints[referencePoints.length - 1]?.date || historyCompare.end_date
  };
}
