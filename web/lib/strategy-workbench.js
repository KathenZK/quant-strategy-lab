export const STRATEGY_LABELS = Object.freeze({
  crowding_reversal: "拥挤度反转",
  donchian_breakout: "Donchian 突破",
  ma_crossover: "双均线交叉",
  momentum_rotation: "动量轮动",
  small_cap_momentum_breakout: "小市值动量突破",
  trend_confirmation: "趋势确认",
});

const numberFormat = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 2,
});

const compactNumberFormat = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 4,
});

const dateFormat = new Intl.DateTimeFormat("zh-CN", {
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

export function metricOf(run, key) {
  const value = run?.backtest_metrics?.[key] ?? run?.[key];
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : null;
}

export function formatNumber(value, fallback = "-") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return fallback;
  }
  return numberFormat.format(Number(value));
}

export function formatMetric(value, fallback = "-") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return fallback;
  }
  return compactNumberFormat.format(Number(value));
}

export function formatPercent(value, fallback = "-") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return fallback;
  }
  return `${(Number(value) * 100).toFixed(2)}%`;
}

export function formatDate(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "-" : dateFormat.format(date);
}

export function shortHash(value, length = 10) {
  return value ? String(value).slice(0, length) : "-";
}

export function runIdentity(run) {
  return run?.manifest_path || run?.run_id || "";
}

export function strategyKeyFromTemplate(template) {
  return String(template?.strategy_type || template?.id || "unknown");
}

export function strategyKeyFromRun(run) {
  return String(run?.strategy_type || run?.signal_name || run?.strategy_name || run?.name || "unknown");
}

export function strategyLabel(value) {
  const key = typeof value === "string" ? value : strategyKeyFromRun(value);
  return STRATEGY_LABELS[key] || key || "-";
}

export function runWindow(run) {
  const searchable = [run?.name, run?.strategy_name, run?.backtest_report_path, run?.manifest_path, run?.registry_profile]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  if (searchable.includes("recent1y_daily") || searchable.includes("daily_recent1y") || searchable.includes("recent1y-daily")) {
    return "1y daily";
  }
  if (searchable.includes("recent3m_daily") || searchable.includes("daily_recent3m") || searchable.includes("daily.recent3m")) {
    return "3m daily";
  }
  if (searchable.includes("recent3m")) {
    return "3m 1h";
  }
  if (searchable.includes("recent1y")) {
    return "1y";
  }
  return run?.registry_profile || "registry";
}

export function buildLabRunHref(run) {
  const params = new URLSearchParams({
    strategy: strategyKeyFromRun(run),
  });
  if (run?.manifest_path) {
    params.set("run", run.manifest_path);
  }
  return `/lab?${params.toString()}`;
}

function compareByGeneratedAt(left, right) {
  return new Date(right?.generated_at || 0).getTime() - new Date(left?.generated_at || 0).getTime();
}

export function bestRunByMetric(runs, key = "sharpe") {
  const scored = runs.filter((run) => metricOf(run, key) !== null);
  if (!scored.length) {
    return null;
  }
  return [...scored].sort((left, right) => metricOf(right, key) - metricOf(left, key))[0];
}

export function runVariantId(run) {
  return run?.variant_id || shortHash(run?.config_hash, 8) || shortHash(run?.run_id, 8);
}

export function symbolLabel(symbol) {
  if (!symbol) {
    return "-";
  }
  return String(symbol).split("/")[0] || String(symbol);
}

function maLabel(factor) {
  const match = String(factor || "").match(/ma_distance_(\d+)/);
  return match ? `${match[1]}MA` : factor || null;
}

function inferSymbolFromRun(run) {
  const text = [run?.name, run?.strategy_name, run?.manifest_path].filter(Boolean).join(" ").toLowerCase();
  if (text.includes("btc")) {
    return "BTC";
  }
  if (text.includes("eth")) {
    return "ETH";
  }
  if (text.includes("sol")) {
    return "SOL";
  }
  return "-";
}

function inferMaPairFromRun(run) {
  const variant = String(run?.variant_id || "");
  const variantMatch = variant.match(/ma(\d+)_ma(\d+)/i);
  if (variantMatch) {
    return [`${variantMatch[1]}MA`, `${variantMatch[2]}MA`];
  }

  const text = [run?.name, run?.strategy_name, run?.manifest_path].filter(Boolean).join(" ");
  const nameMatch = text.match(/ma_crossover_(\d+)_(\d+)/i);
  if (nameMatch) {
    return [`${nameMatch[1]}MA`, `${nameMatch[2]}MA`];
  }

  return [null, null];
}

export function strategyParamsOf(run) {
  const params = run?.strategy_params;
  return params && typeof params === "object" && !Array.isArray(params) ? params : {};
}

export function parameterSummary(run) {
  const params = strategyParamsOf(run);
  const symbols = Array.isArray(run?.symbols) ? run.symbols : [];
  const symbol = symbols.length ? symbolLabel(symbols[0]) : inferSymbolFromRun(run);
  const timeframe = run?.timeframe || (runWindow(run).includes("daily") ? "1d" : "-");

  if ((run?.strategy_type || run?.signal_name) === "ma_crossover") {
    const [inferredFastMa, inferredSlowMa] = inferMaPairFromRun(run);
    return `${symbol} / ${timeframe} / ${maLabel(params.fast_ma_factor) || inferredFastMa || "-"} / ${maLabel(params.slow_ma_factor) || inferredSlowMa || "-"}`;
  }

  const entries = Object.entries(params).slice(0, 4);
  if (!entries.length) {
    return `${symbol} / ${timeframe}`;
  }
  return `${symbol} / ${timeframe} / ${entries.map(([key, value]) => `${key}=${value}`).join(" / ")}`;
}

export function costRatioOf(run) {
  const direct = metricOf(run, "fee_ratio");
  if (direct !== null) {
    return direct;
  }
  const cost = Number(run?.backtest_attribution?.trading_cost_sum);
  const gross = Number(run?.backtest_attribution?.gross_return_sum);
  if (!Number.isFinite(cost) || !Number.isFinite(gross) || gross === 0) {
    return null;
  }
  return cost / Math.abs(gross);
}

export function groupRunsByVariant(runs) {
  const grouped = new Map();
  for (const run of runs) {
    const key = runVariantId(run);
    const existing = grouped.get(key) || {
      id: key,
      runs: [],
      bestRun: null,
      latestRun: null,
    };
    existing.runs.push(run);
    grouped.set(key, existing);
  }

  return [...grouped.values()]
    .map((variant) => {
      const sortedRuns = [...variant.runs].sort(compareByGeneratedAt);
      return {
        ...variant,
        runs: sortedRuns,
        latestRun: sortedRuns[0] ?? null,
        bestRun: bestRunByMetric(sortedRuns) ?? sortedRuns[0] ?? null,
      };
    })
    .sort((left, right) => compareByGeneratedAt(left.latestRun, right.latestRun));
}

export function buildStrategyGroups(templates = [], runs = []) {
  const groups = new Map();

  for (const template of templates) {
    const key = strategyKeyFromTemplate(template);
    groups.set(key, {
      key,
      label: strategyLabel(template.strategy_type || key),
      category: template.category || "strategy",
      description: template.description || "",
      template,
      runs: [],
    });
  }

  for (const run of runs.filter((item) => item?.kind === "workflow_run" || !item?.kind)) {
    const key = strategyKeyFromRun(run);
    const current =
      groups.get(key) ||
      {
        key,
        label: strategyLabel(key),
        category: run.strategy_type || "strategy",
        description: "",
        template: null,
        runs: [],
      };
    current.runs.push(run);
    groups.set(key, current);
  }

  return [...groups.values()]
    .map((group) => {
      const sortedRuns = [...group.runs].sort(compareByGeneratedAt);
      const bestRun = bestRunByMetric(sortedRuns);
      const paperRunCount = sortedRuns.filter((run) => run.paper_report_path || Object.keys(run.paper_summary ?? {}).length > 0).length;
      return {
        ...group,
        runs: sortedRuns,
        variants: groupRunsByVariant(sortedRuns),
        bestRun,
        latestRun: sortedRuns[0] ?? null,
        paperRunCount,
      };
    })
    .sort((left, right) => {
      const leftTime = new Date(left.latestRun?.generated_at || 0).getTime();
      const rightTime = new Date(right.latestRun?.generated_at || 0).getTime();
      if (leftTime !== rightTime) {
        return rightTime - leftTime;
      }
      return left.label.localeCompare(right.label, "zh-CN");
    });
}

export function extractStrategyParams(template) {
  const params = template?.workflow?.strategy?.strategy_params;
  return params && typeof params === "object" && !Array.isArray(params) ? params : {};
}

function serializeYamlValue(value) {
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  if (value === null || value === undefined) {
    return "null";
  }
  const text = String(value);
  return /^[A-Za-z0-9_./:-]+$/.test(text) ? text : JSON.stringify(text);
}

export function coerceParameterValue(rawValue, sampleValue) {
  if (typeof sampleValue === "boolean") {
    return rawValue === true || rawValue === "true";
  }
  if (typeof sampleValue === "number") {
    const numericValue = Number(rawValue);
    return Number.isFinite(numericValue) ? numericValue : sampleValue;
  }
  return rawValue;
}

export function updateYamlStrategyParamsBlock(yaml, params) {
  const lines = String(yaml || "").split("\n");
  const paramLines = Object.entries(params).map(([key, value]) => `    ${key}: ${serializeYamlValue(value)}`);
  const strategyParamsLine = "  strategy_params:";
  const block = [strategyParamsLine, ...paramLines];
  const startIndex = lines.findIndex((line) => /^\s*strategy_params:\s*$/.test(line));

  if (startIndex >= 0) {
    const indent = lines[startIndex].match(/^(\s*)/)?.[1]?.length ?? 0;
    let endIndex = startIndex + 1;
    while (endIndex < lines.length) {
      const line = lines[endIndex];
      const currentIndent = line.match(/^(\s*)/)?.[1]?.length ?? 0;
      if (line.trim() && currentIndent <= indent) {
        break;
      }
      endIndex += 1;
    }
    lines.splice(startIndex, endIndex - startIndex, ...block);
    return lines.join("\n");
  }

  const strategyIndex = lines.findIndex((line) => /^strategy:\s*$/.test(line));
  if (strategyIndex >= 0) {
    let insertIndex = strategyIndex + 1;
    while (insertIndex < lines.length && /^  (name|strategy_type|factor_name|exchange|market_type|benchmark_symbol):/.test(lines[insertIndex])) {
      insertIndex += 1;
    }
    lines.splice(insertIndex, 0, ...block);
    return lines.join("\n");
  }

  return [`strategy:`, ...block, "", String(yaml || "")].join("\n");
}
