import { api } from "@/lib/api";
import { computeTips, outcomeColor, outcomeBg } from "@/lib/tips";
import type { MatchSummary } from "@/types";
import Link from "next/link";

function fmt(iso?: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("de-DE", {
    weekday: "short", day: "2-digit", month: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

// Spiele nach Datum gruppieren
function byDate(matches: MatchSummary[]): Record<string, MatchSummary[]> {
  const result: Record<string, MatchSummary[]> = {};
  for (const m of matches) {
    const day = m.kickoff_utc
      ? new Date(m.kickoff_utc).toLocaleDateString("de-DE", { weekday: "long", day: "2-digit", month: "long" })
      : "Datum unbekannt";
    (result[day] ??= []).push(m);
  }
  return result;
}

export const revalidate = 60;

export default async function TippsPage() {
  let matches: MatchSummary[] = [];
  try {
    const all = await api.matches();
    // Nur Spiele mit Prognosen und bekannten Teams
    matches = all.filter(
      (m) => m.prediction && m.home_team && m.away_team && m.status !== "FINISHED"
    );
  } catch {
    // noop
  }

  const grouped = byDate(matches);
  const days = Object.keys(grouped);

  const totalWithPred = matches.filter((m) => m.prediction).length;

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Tipprunde</h1>
        <p className="text-wm-muted text-sm mt-1">
          Konkrete Ergebnis-Tipps für alle {totalWithPred} Spiele mit Prognose ·
          Modell: Elo + Poisson + 7 Kontextfaktoren
        </p>
      </div>

      {/* Legende */}
      <div className="card flex flex-wrap gap-4 text-xs">
        <div className="flex items-center gap-2">
          <span className="font-bold text-white text-base">2:1</span>
          <span className="text-wm-muted">xG-Tipp (gerundete erwartete Tore)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-wm-muted">(1:1)</span>
          <span className="text-wm-muted">Wahrscheinlichstes Ergebnis laut Modell</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-blue-400 font-bold">Blau</span>
          <span className="text-wm-muted">= Heimsieg</span>
          <span className="text-yellow-400 font-bold ml-2">Gelb</span>
          <span className="text-wm-muted">= Unentschieden</span>
          <span className="text-red-400 font-bold ml-2">Rot</span>
          <span className="text-wm-muted">= Auswärtssieg</span>
        </div>
      </div>

      {matches.length === 0 && (
        <div className="card text-wm-muted text-sm">
          Noch keine Prognosen. "Daten aktualisieren" und "Simulieren" klicken,
          dann <Link href="/api/v1/predict-all" className="underline">POST /predict-all</Link> aufrufen.
        </div>
      )}

      {/* Tage */}
      {days.map((day) => (
        <section key={day} className="space-y-2">
          <h2 className="text-sm font-semibold text-wm-muted uppercase tracking-wider border-b border-wm-border pb-1">
            {day}
          </h2>

          <div className="space-y-1.5">
            {grouped[day].map((match) => {
              const pred = match.prediction;
              if (!pred) return null;

              const { xgTip, modelTip } = computeTips(pred);
              const group = match.group_id ? `Gr. ${match.group_id}` : match.stage.replace(/_/g, " ");

              return (
                <Link key={match.id} href={`/match/${match.id}`}>
                  <div className={`flex items-center gap-3 px-3 py-2.5 rounded-lg border ${outcomeBg(xgTip.outcome)} hover:opacity-90 transition-opacity cursor-pointer`}>

                    {/* Zeit + Gruppe */}
                    <div className="w-28 shrink-0 text-left">
                      <div className="text-xs text-wm-muted">{fmt(match.kickoff_utc).split(",")[1]?.trim() ?? "—"}</div>
                      <div className="text-xs text-wm-muted">{group}</div>
                    </div>

                    {/* Heimteam */}
                    <div className="flex items-center gap-1.5 flex-1 min-w-0 justify-end">
                      <span className="text-sm text-gray-300 truncate">{match.home_team?.name}</span>
                      <span className="text-lg shrink-0">{match.home_team?.flag_emoji ?? "🏳️"}</span>
                    </div>

                    {/* TippBox */}
                    <div className="text-center shrink-0 w-28">
                      <div className={`text-xl font-black ${outcomeColor(xgTip.outcome)}`}>
                        {xgTip.score}
                      </div>
                      {modelTip && modelTip.score !== xgTip.score && (
                        <div className="text-xs text-wm-muted">({modelTip.score})</div>
                      )}
                    </div>

                    {/* Auswärtsteam */}
                    <div className="flex items-center gap-1.5 flex-1 min-w-0">
                      <span className="text-lg shrink-0">{match.away_team?.flag_emoji ?? "🏳️"}</span>
                      <span className="text-sm text-gray-300 truncate">{match.away_team?.name}</span>
                    </div>

                    {/* Wahrscheinlichkeiten */}
                    <div className="w-24 shrink-0 text-right hidden sm:block">
                      <div className="text-xs text-wm-muted">
                        {(pred.prob_home_win * 100).toFixed(0)}% ·{" "}
                        {(pred.prob_draw * 100).toFixed(0)}% ·{" "}
                        {(pred.prob_away_win * 100).toFixed(0)}%
                      </div>
                      <div className="text-xs text-wm-muted">
                        xG {pred.xg_home.toFixed(1)}:{pred.xg_away.toFixed(1)}
                      </div>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
