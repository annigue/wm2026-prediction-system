import type { PredictionSummary, PredictionDetail } from "@/types";

export type Outcome = "home" | "draw" | "away";

export interface OfficialForecast {
  outcome: Outcome;
  score: string;
  prob: number;
  probs: { home: number; draw: number; away: number };
  xg: { home: number; away: number };
  top_scorelines: { score: string; prob: number }[];
  confidence: { level: string; decisiveness: number };
  market: {
    available: boolean;
    weight: number;
    fair_1x2: { home: number; draw: number; away: number } | null;
    divergence: number | null;
    agreement: string;
  };
}

function condMode(dist: Record<string, number>, outcome: Outcome): string | null {
  const sign = outcome === "home" ? 1 : outcome === "away" ? -1 : 0;
  let best: string | null = null;
  let bestP = -1;
  for (const [k, p] of Object.entries(dist)) {
    const [i, j] = k.split(":").map(Number);
    const r = i > j ? 1 : i < j ? -1 : 0;
    if (r === sign && p > bestP) { bestP = p; best = k; }
  }
  return best;
}

/**
 * Offizielle (markt-kalibrierte) Prognose. Nutzt explanation.official aus dem Backend;
 * fällt für alte Prognosen ohne dieses Feld sauber auf das reine Modell zurück.
 */
export function officialForecast(pred: PredictionDetail): OfficialForecast {
  const o = pred.explanation?.official;
  if (o) return o as OfficialForecast;

  const probs = { home: pred.prob_home_win, draw: pred.prob_draw, away: pred.prob_away_win };
  const outcome: Outcome =
    probs.home >= probs.draw && probs.home >= probs.away ? "home"
      : probs.away >= probs.draw ? "away" : "draw";
  const d = Math.max(probs.home, probs.draw, probs.away);
  const level = d >= 0.55 ? "hoch" : d >= 0.42 ? "mittel" : "niedrig";
  const score =
    (pred.score_distribution && condMode(pred.score_distribution, outcome)) ||
    pred.top_scoreline ||
    `${Math.round(pred.xg_home)}:${Math.round(pred.xg_away)}`;
  return {
    outcome, score, prob: d, probs,
    xg: { home: pred.xg_home, away: pred.xg_away },
    top_scorelines: pred.top_scorelines ?? [],
    confidence: { level, decisiveness: d },
    market: { available: false, weight: 0, fair_1x2: null, divergence: null, agreement: "kein_markt" },
  };
}

export interface Tip {
  score: string;        // z.B. "2:1"
  method: "xg" | "top_scoreline" | "official";
  label: string;        // Erklärung
  outcome: "home" | "draw" | "away";
  confidence?: number;  // Wahrscheinlichkeit dieses genauen Ergebnisses
}

/**
 * DER empfohlene Tipp = die offizielle (markt-kalibrierte) Prognose — identisch zu dem,
 * was die Match-Detailseite zeigt. Fällt für alte Prognosen ohne `official` auf den xG-Tipp zurück.
 * So zeigen Tipps-Seite und Spiel-Detail garantiert dieselbe EINE Prognose.
 */
export function recommendedTip(pred: PredictionSummary): Tip {
  const o = pred.official;
  if (o && o.score && o.outcome) {
    return {
      score: o.score,
      method: "official",
      label: "offizielle Prognose",
      outcome: o.outcome,
      confidence: o.prob,
    };
  }
  return computeTips(pred).xgTip;
}

/**
 * Berechnet den konkreten Tipp aus einer Spielprognose.
 *
 * Primär: xG-Tipp (gerundete Expected Goals) — zeigt den Stärkeunterschied,
 * vermeidet Wiederholung gleicher Scores, intuitiver für Tipprunden.
 *
 * Sekundär: Wahrscheinlichstes Ergebnis (top_scorelines[0]) aus dem Modell.
 */
export function computeTips(pred: PredictionSummary): {
  xgTip: Tip;
  modelTip: Tip | null;
} {
  // ── xG-Tipp ─────────────────────────────────────────────────────────────
  const h = Math.round(pred.xg_home);
  const a = Math.round(pred.xg_away);
  const xgScore = `${h}:${a}`;
  const xgOutcome: Tip["outcome"] = h > a ? "home" : h < a ? "away" : "draw";

  const xgTip: Tip = {
    score: xgScore,
    method: "xg",
    label: `xG ${pred.xg_home.toFixed(2)} : ${pred.xg_away.toFixed(2)}`,
    outcome: xgOutcome,
  };

  // ── Modell-Tipp (wahrscheinlichstes Ergebnis) ────────────────────────────
  let modelTip: Tip | null = null;
  if (pred.top_scoreline) {
    const [sh, sa] = pred.top_scoreline.split(":").map(Number);
    const mOutcome: Tip["outcome"] = sh > sa ? "home" : sh < sa ? "away" : "draw";
    modelTip = {
      score: pred.top_scoreline,
      method: "top_scoreline",
      label: "wahrscheinlichstes Ergebnis",
      outcome: mOutcome,
    };
  }

  return { xgTip, modelTip };
}

// ── Tipp-Auswertung gegen das tatsächliche Ergebnis (Kicktipp-Standard) ──────
// Exakt = 4 · gleiche Tordifferenz (inkl. beide Remis) = 3 · Tendenz = 2 · sonst 0.
// Identisch zur Backend-Logik (tipping_engine._points).
export interface TipEval {
  points: number;
  kind: "exact" | "diff" | "tendency" | "miss";
  label: string;
}

export function evaluateTip(
  tipScore: string,
  result: { home_goals: number; away_goals: number },
): TipEval | null {
  const parts = tipScore.split(":").map((n) => parseInt(n.trim(), 10));
  if (parts.length !== 2 || parts.some((n) => Number.isNaN(n))) return null;
  const [ti, tj] = parts;
  const ai = result.home_goals;
  const aj = result.away_goals;
  if (ti === ai && tj === aj) return { points: 4, kind: "exact", label: "Exakt" };
  const td = ti - tj;
  const ad = ai - aj;
  if (td === ad) return { points: 3, kind: "diff", label: "Tordifferenz" };
  if ((td > 0 && ad > 0) || (td < 0 && ad < 0)) return { points: 2, kind: "tendency", label: "Tendenz" };
  return { points: 0, kind: "miss", label: "Daneben" };
}

export function evalColor(kind: TipEval["kind"]) {
  return kind === "exact"
    ? "text-green-400"
    : kind === "diff"
    ? "text-emerald-400"
    : kind === "tendency"
    ? "text-yellow-400"
    : "text-red-400";
}

export function outcomeColor(outcome: Tip["outcome"]) {
  return outcome === "home" ? "text-blue-400" : outcome === "away" ? "text-red-400" : "text-yellow-400";
}

export function outcomeBg(outcome: Tip["outcome"]) {
  return outcome === "home" ? "bg-blue-900/30 border-blue-700" : outcome === "away" ? "bg-red-900/30 border-red-700" : "bg-yellow-900/30 border-yellow-700";
}
