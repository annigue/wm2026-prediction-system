interface Factor {
  name: string;
  value: string;
  elo_delta: number;
  direction: "home" | "away" | "neutral";
  weight: number;
}

interface ExplanationData {
  summary: string;
  elo_home: number;
  elo_away: number;
  elo_delta: number;
  feature_delta: number;
  adjusted_elo_home: number;
  adjusted_elo_away: number;
  factors: Factor[];
}

interface Props {
  explanation: ExplanationData;
  homeName: string;
  awayName: string;
}

export function FactorExplanation({ explanation, homeName, awayName }: Props) {
  const maxDelta = Math.max(...explanation.factors.map(f => Math.abs(f.elo_delta)), 1);

  return (
    <div className="space-y-4">
      {/* Summary */}
      <p className="text-sm text-gray-300">{explanation.summary}</p>

      {/* Elo-Übersicht */}
      <div className="grid grid-cols-3 gap-2 text-center text-sm">
        <div className="card">
          <div className="text-xs text-wm-muted mb-1">{homeName}</div>
          <div className="font-mono font-bold text-blue-400">{explanation.elo_home}</div>
          <div className="text-xs text-wm-muted">→ {explanation.adjusted_elo_home}</div>
        </div>
        <div className="card flex flex-col items-center justify-center">
          <div className="text-xs text-wm-muted">Elo-Diff</div>
          <div className={`font-bold text-lg ${explanation.elo_delta > 0 ? "text-blue-400" : explanation.elo_delta < 0 ? "text-red-400" : "text-gray-400"}`}>
            {explanation.elo_delta > 0 ? "+" : ""}{explanation.elo_delta}
          </div>
          {explanation.feature_delta !== 0 && (
            <div className={`text-xs ${explanation.feature_delta > 0 ? "text-blue-300" : "text-red-300"}`}>
              Kontext: {explanation.feature_delta > 0 ? "+" : ""}{explanation.feature_delta}
            </div>
          )}
        </div>
        <div className="card">
          <div className="text-xs text-wm-muted mb-1">{awayName}</div>
          <div className="font-mono font-bold text-red-400">{explanation.elo_away}</div>
          <div className="text-xs text-wm-muted">→ {explanation.adjusted_elo_away}</div>
        </div>
      </div>

      {/* Faktoren */}
      {explanation.factors.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-wm-muted uppercase tracking-wider">
            Kontextfaktoren
          </h4>
          {explanation.factors.map((f, i) => {
            const barWidth = Math.abs(f.elo_delta) / maxDelta * 100;
            const isHome   = f.direction === "home";
            const isNeutral= f.direction === "neutral";
            const barColor = isNeutral ? "bg-gray-600" : isHome ? "bg-blue-600" : "bg-red-600";
            const label    = isNeutral ? "neutral" : isHome ? `+${f.elo_delta} für ${homeName}` : `${f.elo_delta} für ${awayName}`;

            return (
              <div key={i} className="space-y-0.5">
                <div className="flex justify-between text-xs">
                  <span className="text-gray-300 font-medium">{f.name}</span>
                  <span className={`text-xs ${isNeutral ? "text-wm-muted" : isHome ? "text-blue-400" : "text-red-400"}`}>
                    {label}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${barColor} transition-all`}
                      style={{ width: `${barWidth}%` }}
                    />
                  </div>
                </div>
                <div className="text-xs text-wm-muted">{f.value}</div>
              </div>
            );
          })}
        </div>
      )}

      <p className="text-xs text-wm-muted border-t border-wm-border pt-3">
        Modell: Elo-Rating + 7 Kontextfaktoren → angepasste Elo-Differenz → Poisson Goal Model (Dixon-Coles-Korrektur)
      </p>
    </div>
  );
}
