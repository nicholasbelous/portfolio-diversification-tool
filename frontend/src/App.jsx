import { useMemo, useState } from "react";

import {
  analyzePortfolio,
  comparePortfolioHistory,
  fetchTopVolatility,
  optimizePortfolio
} from "./api/client";
import { formatMoney, formatNumber } from "./lib/format";
import { buildHoldingPayload, clampNumber, mergeWarnings } from "./lib/portfolio";
import AnalysisPage from "./pages/AnalysisPage";
import InputPage from "./pages/InputPage";
import OptimizationPage from "./pages/OptimizationPage";

const PAGE_ORDER = ["input", "analysis", "optimization"];
const PAGE_LABELS = {
  input: "Portfolio Setup",
  analysis: "Risk Diagnosis",
  optimization: "Optimization Plan"
};

function stepState(stepKey, currentPage, hasAnalysis, hasOptimization) {
  if (stepKey === "input") {
    return { enabled: true, completed: currentPage !== "input" };
  }
  if (stepKey === "analysis") {
    return {
      enabled: hasAnalysis,
      completed: currentPage === "optimization"
    };
  }
  return {
    enabled: hasOptimization,
    completed: false
  };
}

export default function App() {
  const [mode, setMode] = useState("amount");
  const [rows, setRows] = useState([
    { ticker: "AAPL", value: "7000" },
    { ticker: "MSFT", value: "5000" },
    { ticker: "NVDA", value: "3000" },
    { ticker: "JPM", value: "2500" }
  ]);

  const [currentPage, setCurrentPage] = useState("input");
  const [transitionDirection, setTransitionDirection] = useState("forward");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [warnings, setWarnings] = useState([]);

  const [analysis, setAnalysis] = useState(null);
  const [optimization, setOptimization] = useState(null);
  const [historyCompare, setHistoryCompare] = useState(null);

  const [chartRange, setChartRange] = useState("1Y");
  const [maxChanges, setMaxChanges] = useState(5);
  const [tradeCostRate, setTradeCostRate] = useState(0.0015);
  const [topVolatility, setTopVolatility] = useState([]);

  const holdingPayload = useMemo(() => buildHoldingPayload(mode, rows), [mode, rows]);
  const hasEnoughInput = holdingPayload.length >= 2;
  const totalAmount = useMemo(
    () => holdingPayload.reduce((sum, row) => sum + Number(row.amount || 0), 0),
    [holdingPayload]
  );

  const hasAnalysis = Boolean(analysis);
  const hasOptimization = Boolean(optimization);

  function goToPage(nextPage, force = false) {
    if (!PAGE_ORDER.includes(nextPage)) {
      return;
    }

    if (!force) {
      if (nextPage === "analysis" && !hasAnalysis) {
        return;
      }
      if (nextPage === "optimization" && !hasOptimization) {
        return;
      }
    }

    const currentIndex = PAGE_ORDER.indexOf(currentPage);
    const nextIndex = PAGE_ORDER.indexOf(nextPage);
    setTransitionDirection(nextIndex >= currentIndex ? "forward" : "backward");
    setCurrentPage(nextPage);
  }

  async function loadTopVolatility() {
    try {
      const data = await fetchTopVolatility(8);
      setTopVolatility(Array.isArray(data.items) ? data.items : []);
    } catch {
      setTopVolatility([]);
    }
  }

  async function handleAnalyze() {
    if (!hasEnoughInput) {
      setError("Add at least two valid holdings before analyzing.");
      return;
    }

    setLoading(true);
    setError("");
    setWarnings([]);
    setOptimization(null);
    setHistoryCompare(null);

    try {
      const response = await analyzePortfolio({ holdings: holdingPayload });
      const data = response.data;
      setAnalysis(data);
      setWarnings(data?.warnings || []);
      goToPage("analysis", true);

      if (!topVolatility.length) {
        void loadTopVolatility();
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Analysis request failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleOptimize() {
    if (!hasEnoughInput) {
      setError("Add at least two valid holdings before optimizing.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await optimizePortfolio({
        holdings: holdingPayload,
        max_changes: Number(maxChanges),
        transaction_cost_rate: Number(tradeCostRate),
        include_sp500_additions: true,
        include_etfs: true
      });

      const optimizationData = response.data;
      setOptimization(optimizationData);
      setWarnings(optimizationData?.warnings || []);

      const optimizedWeights = Array.isArray(optimizationData?.optimized_weights)
        ? optimizationData.optimized_weights.map((row) => ({
            ticker: row.ticker,
            weight: Number(row.weight)
          }))
        : [];

      try {
        const historyResponse = await comparePortfolioHistory({
          holdings: holdingPayload,
          optimized_weights: optimizedWeights,
          lookback_days: 504,
          include_benchmark: true
        });

        setHistoryCompare(historyResponse.data || null);
        const historyWarnings = historyResponse.data?.warnings || [];
        if (historyWarnings.length) {
          setWarnings((prev) => mergeWarnings(prev, historyWarnings));
        }
      } catch {
        setHistoryCompare(null);
        setWarnings((prev) =>
          mergeWarnings(
            prev,
            "Historical comparison chart could not be loaded. Optimization metrics are still valid."
          )
        );
      }

      goToPage("optimization", true);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Optimization request failed.");
    } finally {
      setLoading(false);
    }
  }

  function handleStartOver() {
    setTransitionDirection("backward");
    setCurrentPage("input");
    setAnalysis(null);
    setOptimization(null);
    setHistoryCompare(null);
    setWarnings([]);
    setError("");
  }

  function updateRow(index, key, value) {
    setRows((prev) => prev.map((row, rowIndex) => (rowIndex === index ? { ...row, [key]: value } : row)));
  }

  function addRow() {
    setRows((prev) => [...prev, { ticker: "", value: "" }]);
  }

  function removeRow(index) {
    setRows((prev) => prev.filter((_, rowIndex) => rowIndex !== index));
  }

  const pageContent =
    currentPage === "input" ? (
      <InputPage
        mode={mode}
        onChangeMode={setMode}
        rows={rows}
        onUpdateRow={updateRow}
        onAddRow={addRow}
        onRemoveRow={removeRow}
        onAnalyze={handleAnalyze}
        loading={loading}
        hasEnoughInput={hasEnoughInput}
        validHoldings={holdingPayload.length}
        totalAmount={mode === "amount" ? totalAmount : null}
      />
    ) : null;

  const analysisPage =
    currentPage === "analysis" && analysis ? (
      <AnalysisPage
        analysis={analysis}
        topVolatility={topVolatility}
        maxChanges={maxChanges}
        onChangeMaxChanges={(value) =>
          setMaxChanges(
            clampNumber(value, {
              min: 1,
              max: 20,
              fallback: 5
            })
          )
        }
        tradeCostRate={tradeCostRate}
        onChangeTradeCostRate={(value) =>
          setTradeCostRate(
            clampNumber(value, {
              min: 0,
              max: 0.05,
              fallback: 0.0015
            })
          )
        }
        onBack={() => goToPage("input", true)}
        onOptimize={handleOptimize}
        loading={loading}
      />
    ) : null;

  const optimizationPage =
    currentPage === "optimization" && optimization ? (
      <OptimizationPage
        optimization={optimization}
        historyCompare={historyCompare}
        chartRange={chartRange}
        onChangeChartRange={setChartRange}
        onBack={() => goToPage("analysis", true)}
        onStartOver={handleStartOver}
      />
    ) : null;

  return (
    <main className="app-shell">
      <div className="bg-shape bg-shape-a" />
      <div className="bg-shape bg-shape-b" />

      <header className="app-header">
        <p className="eyebrow">Portfolio Diversification Studio</p>
        <h1>From Current Risk to Practical Rebalance Plan</h1>
        <p>
          Three clear steps: define your portfolio, diagnose risk, then review a constrained optimization with realistic
          assumptions and clear trade actions.
        </p>

        <div className="header-stats">
          <div>
            <span>Valid holdings</span>
            <strong>{formatNumber(holdingPayload.length, 0)}</strong>
          </div>
          <div>
            <span>Input mode</span>
            <strong>{mode === "amount" ? "Dollar" : "Weight"}</strong>
          </div>
          <div>
            <span>Input total</span>
            <strong>{mode === "amount" ? formatMoney(totalAmount) : "N/A"}</strong>
          </div>
        </div>
      </header>

      <nav className="step-nav" aria-label="Workflow steps">
        {PAGE_ORDER.map((stepKey, index) => {
          const state = stepState(stepKey, currentPage, hasAnalysis, hasOptimization);
          const active = currentPage === stepKey;
          return (
            <button
              key={stepKey}
              type="button"
              className={`step-link ${active ? "active" : ""} ${state.completed ? "completed" : ""}`}
              onClick={() => goToPage(stepKey)}
              disabled={!state.enabled}
            >
              <span>{index + 1}</span>
              <div>
                <strong>{PAGE_LABELS[stepKey]}</strong>
                <small>{state.enabled ? "Ready" : "Locked"}</small>
              </div>
            </button>
          );
        })}
      </nav>

      {error ? (
        <section className="alert-card alert-error">
          <h3>Request Error</h3>
          <p>{error}</p>
        </section>
      ) : null}

      {warnings.length ? (
        <section className="alert-card alert-warning">
          <h3>Heads Up</h3>
          <ul>
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="page-stage">
        <div key={`${currentPage}-${transitionDirection}`} className={`page-card transition-${transitionDirection}`}>
          {pageContent}
          {analysisPage}
          {optimizationPage}
        </div>
      </section>
    </main>
  );
}
