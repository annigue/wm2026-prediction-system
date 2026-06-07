import type { PredictionSummary } from "@/types";

export interface Tip {
  score: string;        // z.B. "2:1"
  method: "xg" | "top_scoreline";
  label: string;        // Erklärung
  outcome: "home" | "draw" | "away";
  confidence?: number;  // Wahrscheinlichkeit dieses genauen Ergebnisses
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

export function outcomeColor(outcome: Tip["outcome"]) {
  return outcome === "home" ? "text-blue-400" : outcome === "away" ? "text-red-400" : "text-yellow-400";
}

export function outcomeBg(outcome: Tip["outcome"]) {
  return outcome === "home" ? "bg-blue-900/30 border-blue-700" : outcome === "away" ? "bg-red-900/30 border-red-700" : "bg-yellow-900/30 border-yellow-700";
}
