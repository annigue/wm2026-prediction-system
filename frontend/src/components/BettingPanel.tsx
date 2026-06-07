import { api } from "@/lib/api";

interface BetOption {
  market: string;
  selection: string;
  probability: number;
  odds: number;
  implied_prob: number;
  ev: number;
  ev_label: string;
  confidence: string;
  risk: string;
  rationale: string;
  is_value: boolean;
  odds_estimated: boolean;
  market_prob: number;
  edge: number;
}

interface BettingReport {
  best_bet: BetOption | null;
  safe_bet: BetOption | null;
  value_bets: BetOption[];
  scoreline_tip: string | null;
  model_confidence: string;
  ev_calculable: boolean;
  disclaimer: string;
}

function riskBadge(risk: string) {
  const cls =
    risk === "LOW" ? "badge-green" : risk === "MEDIUM" ? "badge-yellow" : "badge-red";
  const label = risk === "LOW" ? "Geringes Risiko" : risk === "MEDIUM" ? "Mittleres Risiko" : "Hohes Risiko";
  return <span className={cls}>{label}</span>;
}

function BetCard({ bet, accent, title }: { bet: BetOption; accent: string; title: string }) {
  return (
    <div className={`rounded-lg border ${accent} p-3 space-y-2`}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-wm-muted">{title}</span>
        {riskBadge(bet.risk)}
      </div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-bold text-white">{bet.selection}</span>
        <span className="text-xs text-wm-muted">{bet.market}</span>
      </div>
      <div className="flex items-center gap-3 text-sm flex-wrap">
        <span className="text-gray-300">Quote <b className="text-white">{bet.odds.toFixed(2)}</b></span>
        <span className={`font-bold ${bet.ev >= 0 ? "text-green-400" : "text-red-400"}`}>
          EV {bet.ev_label}
        </span>
        <span className={`text-xs font-medium ${bet.edge >= 0 ? "text-green-300" : "text-red-300"}`}>
          Edge {bet.edge >= 0 ? "+" : ""}{(bet.edge * 100).toFixed(1)}pp
        </span>
        <span className="text-wm-muted text-xs">
          {(bet.probability * 100).toFixed(0)}% Modell vs {(bet.market_prob * 100).toFixed(0)}% Markt
        </span>
      </div>
      <p className="text-xs text-wm-muted">{bet.rationale}</p>
      {bet.odds_estimated && (
        <p className="text-[10px] text-wm-muted italic">Quote geschätzt (keine echte Marktquote)</p>
      )}
    </div>
  );
}

export async function BettingPanel({ matchId }: { matchId: string }) {
  let report: BettingReport | null = null;
  try {
    report = await api.bets(matchId);
  } catch {
    return null;
  }
  if (!report) return null;

  const hasValue = report.value_bets && report.value_bets.length > 0;

  return (
    <div className="card space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white">💰 Wett-Empfehlungen</h3>
        <span className="text-xs text-wm-muted">Modell-Konfidenz: {report.model_confidence}</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {report.best_bet && (
          <BetCard bet={report.best_bet} title="🎯 Best Bet (höchster EV)" accent="border-wm-gold/40 bg-wm-gold/5" />
        )}
        {report.safe_bet && (
          <BetCard bet={report.safe_bet} title="🛡️ Safe Bet (sicher)" accent="border-green-700/40 bg-green-900/10" />
        )}
      </div>

      {/* Value Bets */}
      {hasValue && (
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-wm-muted uppercase tracking-wider">
            Value Bets (EV ≥ +2%)
          </h4>
          {report.value_bets.map((bet, i) => (
            <div key={i} className="flex items-center gap-3 text-sm px-2 py-1.5 rounded-lg bg-white/5">
              <span className="font-medium text-white flex-1">{bet.selection}</span>
              <span className="text-xs text-wm-muted">{bet.market}</span>
              <span className="text-gray-300">@ {bet.odds.toFixed(2)}</span>
              <span className="text-green-400 font-bold w-14 text-right">{bet.ev_label}</span>
            </div>
          ))}
        </div>
      )}

      {!hasValue && (
        <p className="text-xs text-wm-muted">
          Keine Value Bets über +2% EV — der (geschätzte) Markt bietet keinen positiven Erwartungswert.
          Echte Quoten via API-Parameter übergeben für reale Value-Erkennung.
        </p>
      )}

      {/* Scoreline */}
      {report.scoreline_tip && (
        <div className="flex items-center gap-2 text-sm border-t border-wm-border pt-3">
          <span className="text-wm-muted">Ergebnis-Tipp:</span>
          <span className="font-bold text-white">{report.scoreline_tip}</span>
        </div>
      )}

      <p className="text-[10px] text-wm-muted italic border-t border-wm-border pt-2">
        {report.disclaimer}
      </p>
    </div>
  );
}
