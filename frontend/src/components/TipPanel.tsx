import { api } from "@/lib/api";

export async function TipPanel({ matchId }: { matchId: string }) {
  let tip: any = null;
  try {
    tip = await api.tip(matchId);
  } catch {
    return null;
  }
  if (!tip) return null;

  const confColor =
    tip.confidence === "HIGH" ? "text-green-400" :
    tip.confidence === "MEDIUM" ? "text-yellow-400" : "text-wm-muted";

  const differsFromModal = tip.recommended_score !== tip.modal_score;

  return (
    <div className="card border-purple-800/40 bg-purple-950/10 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white">🏆 Tippspiel-Empfehlung</h3>
        <span className={`text-xs font-medium ${confColor}`}>Konfidenz: {tip.confidence}</span>
      </div>

      <div className="flex items-center gap-6 flex-wrap">
        {/* Punktoptimaler Tipp */}
        <div className="text-center">
          <div className="text-4xl font-black text-purple-300">{tip.recommended_score}</div>
          <div className="text-xs text-wm-muted mt-1">Punktoptimal</div>
          <div className="text-xs text-wm-muted">Ø {tip.expected_points} Pkt</div>
        </div>

        {differsFromModal && (
          <>
            <div className="border-l border-wm-border h-12 hidden sm:block" />
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-400">{tip.modal_score}</div>
              <div className="text-xs text-wm-muted mt-1">Wahrscheinlichstes</div>
              <div className="text-xs text-wm-muted">{(tip.modal_probability * 100).toFixed(0)}%</div>
            </div>
          </>
        )}

        <p className="flex-1 text-xs text-gray-300 min-w-[200px]">{tip.rationale}</p>
      </div>

      {/* Top-Kandidaten */}
      <div className="flex flex-wrap gap-2 border-t border-wm-border pt-2">
        {tip.top_candidates?.slice(0, 5).map((c: any, i: number) => (
          <span
            key={i}
            className={`text-xs px-2 py-0.5 rounded ${i === 0 ? "bg-purple-900/40 text-purple-200" : "bg-gray-800 text-wm-muted"}`}
          >
            {c.score} ({c.expected_points})
          </span>
        ))}
      </div>

      <p className="text-[10px] text-wm-muted italic">
        Maximiert erwartete Punkte (4=exakt / 3=Tordifferenz / 2=Tendenz), nicht nur Wahrscheinlichkeit.
      </p>
    </div>
  );
}
