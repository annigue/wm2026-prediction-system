import { api } from "@/lib/api";
import { ProbabilityBar } from "@/components/ui/ProbabilityBar";
import { ScoreHeatmap } from "@/components/ui/ScoreHeatmap";
import { FactorExplanation } from "@/components/ui/FactorExplanation";
import { ResultFormWrapper } from "@/components/ResultFormWrapper";
import { BettingPanel } from "@/components/BettingPanel";
import { TipPanel } from "@/components/TipPanel";
import { computeTips, outcomeColor, outcomeBg } from "@/lib/tips";
import Link from "next/link";

function fmt(iso?: string) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("de-DE", {
    weekday: "long", day: "2-digit", month: "long",
    hour: "2-digit", minute: "2-digit",
  }) + " Uhr";
}

export const revalidate = 60;

// Alle Spiele mit bekannten Teams beim Build vorrendern → erster Besuch sofort.
export async function generateStaticParams() {
  try {
    const matches = await api.matches();
    return matches.filter((m) => m.home_team && m.away_team).map((m) => ({ id: m.id }));
  } catch {
    return [];
  }
}

export default async function MatchPage({ params }: { params: { id: string } }) {
  let match: any = null;
  try {
    match = await api.match(params.id);
  } catch {
    return (
      <div className="card text-red-400">Spiel nicht gefunden: {params.id}</div>
    );
  }

  const pred = match?.prediction;
  const result = match?.result;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Breadcrumb */}
      <div className="text-xs text-wm-muted">
        <Link href="/matches" className="hover:text-white">← Alle Spiele</Link>
        {match?.group_id && (
          <> · <Link href="/groups" className="hover:text-white">Gruppe {match.group_id}</Link></>
        )}
      </div>

      {/* Header: Teams + Ergebnis/Prognose */}
      <div className="card space-y-4">
        {/* Teams */}
        <div className="flex items-center justify-between gap-4">
          <div className="flex-1 text-center">
            <div className="text-4xl mb-1">{match.home_team?.flag_emoji ?? "🏳️"}</div>
            <div className="font-bold text-lg">{match.home_team?.name ?? "TBD"}</div>
            {match.home_team?.elo_rating && (
              <div className="text-xs text-wm-muted">Elo {Math.round(match.home_team.elo_rating)}</div>
            )}
          </div>

          <div className="text-center px-4">
            {result ? (
              <div className="font-black text-4xl text-white">
                {result.home_goals} : {result.away_goals}
              </div>
            ) : (
              <div className="text-wm-muted text-sm">vs</div>
            )}
            <div className="text-xs text-wm-muted mt-1">{fmt(match.kickoff_utc)}</div>
            <div className="text-xs text-wm-muted">{match.venue_name ?? ""}</div>
            <div className="mt-1 space-y-2">
              {match.status === "FINISHED" ? (
                <span className="badge-gray">Abgeschlossen</span>
              ) : match.status === "LIVE" ? (
                <span className="badge-green animate-pulse">LIVE</span>
              ) : (
                <span className="badge-yellow">Geplant</span>
              )}
              {/* Ergebnis-Eingabe (nur für geplante/laufende Spiele mit bekannten Teams) */}
              {match.status !== "FINISHED" && match.home_team && match.away_team && (
                <ResultFormWrapper
                  matchId={match.id}
                  homeName={match.home_team.name ?? "Heim"}
                  awayName={match.away_team.name ?? "Auswärts"}
                  homeFlag={match.home_team.flag_emoji ?? "🏳️"}
                  awayFlag={match.away_team.flag_emoji ?? "🏳️"}
                />
              )}
            </div>
          </div>

          <div className="flex-1 text-center">
            <div className="text-4xl mb-1">{match.away_team?.flag_emoji ?? "🏳️"}</div>
            <div className="font-bold text-lg">{match.away_team?.name ?? "TBD"}</div>
            {match.away_team?.elo_rating && (
              <div className="text-xs text-wm-muted">Elo {Math.round(match.away_team.elo_rating)}</div>
            )}
          </div>
        </div>

        {/* Prognose-Balken */}
        {pred && match.status !== "FINISHED" && (
          <ProbabilityBar
            homeProb={pred.prob_home_win}
            drawProb={pred.prob_draw}
            awayProb={pred.prob_away_win}
            homeLabel={match.home_team?.short_name ?? "Heim"}
            awayLabel={match.away_team?.short_name ?? "Auswärts"}
          />
        )}
      </div>

      {pred && match.status !== "FINISHED" && (() => {
        const { xgTip, modelTip } = computeTips(pred);
        return (
          <div className={`card border ${outcomeBg(xgTip.outcome)} space-y-3`}>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-white">🎯 Modell-Tipp</h3>
              <Link href="/tipps" className="text-xs text-wm-muted hover:text-white">
                Alle Tipps →
              </Link>
            </div>
            <div className="flex items-center gap-6 flex-wrap">
              {/* xG-Tipp */}
              <div className="text-center">
                <div className={`text-4xl font-black ${outcomeColor(xgTip.outcome)}`}>
                  {xgTip.score}
                </div>
                <div className="text-xs text-wm-muted mt-1">xG-Tipp</div>
                <div className="text-xs text-wm-muted">{xgTip.label}</div>
              </div>

              {/* Trennlinie */}
              <div className="border-l border-wm-border h-12 hidden sm:block" />

              {/* Wahrscheinlichstes Ergebnis */}
              {modelTip && (
                <div className="text-center">
                  <div className={`text-2xl font-bold ${outcomeColor(modelTip.outcome)}`}>
                    {modelTip.score}
                  </div>
                  <div className="text-xs text-wm-muted mt-1">wahrscheinlichstes Ergebnis</div>
                </div>
              )}

              {/* Outcome-Text */}
              <div className="flex-1 text-sm text-gray-300">
                {xgTip.outcome === "home" && (
                  <><span className="font-bold text-blue-400">{match.home_team?.name}</span> gewinnt (Heimsieg)</>
                )}
                {xgTip.outcome === "away" && (
                  <><span className="font-bold text-red-400">{match.away_team?.name}</span> gewinnt (Auswärtssieg)</>
                )}
                {xgTip.outcome === "draw" && (
                  <span className="font-bold text-yellow-400">Unentschieden</span>
                )}
                <div className="text-xs text-wm-muted mt-1">
                  Sieg {match.home_team?.short_name} {(pred.prob_home_win * 100).toFixed(0)}% ·
                  Unentschieden {(pred.prob_draw * 100).toFixed(0)}% ·
                  Sieg {match.away_team?.short_name} {(pred.prob_away_win * 100).toFixed(0)}%
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {pred && (
        <>
          {/* Expected Goals + Top Scorelines */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="card space-y-3">
              <h3 className="text-sm font-semibold text-white">Expected Goals (xG)</h3>
              <div className="flex justify-around text-center">
                <div>
                  <div className="text-2xl font-bold text-blue-400">{pred.xg_home}</div>
                  <div className="text-xs text-wm-muted">{match.home_team?.name}</div>
                </div>
                <div className="text-wm-muted self-center">:</div>
                <div>
                  <div className="text-2xl font-bold text-red-400">{pred.xg_away}</div>
                  <div className="text-xs text-wm-muted">{match.away_team?.name}</div>
                </div>
              </div>
              <p className="text-xs text-wm-muted">
                Erwartete Tore basierend auf angepasster Elo-Differenz.
              </p>
            </div>

            <div className="card space-y-2">
              <h3 className="text-sm font-semibold text-white">Wahrscheinlichste Ergebnisse</h3>
              {pred.top_scorelines?.map((s: any, i: number) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="font-mono text-sm font-bold w-8 text-center
                    text-white">{s.score}</span>
                  <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-wm-gold rounded-full"
                      style={{ width: `${(s.prob / pred.top_scorelines[0].prob) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs text-wm-muted w-10 text-right">
                    {(s.prob * 100).toFixed(1)}%
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Tippspiel-Empfehlung (Expected-Points-optimal) */}
          {match.status !== "FINISHED" && <TipPanel matchId={match.id} />}

          {/* Betting Decision Engine */}
          {match.status !== "FINISHED" && <BettingPanel matchId={match.id} />}

          {/* Score-Heatmap */}
          {pred.score_distribution && (
            <div className="card space-y-3">
              <h3 className="text-sm font-semibold text-white">Scoreline-Verteilung</h3>
              <ScoreHeatmap distribution={pred.score_distribution} maxGoals={5} />
            </div>
          )}

          {/* Erklärung */}
          {pred.explanation && (
            <div className="card space-y-3">
              <h3 className="text-sm font-semibold text-white">Modell-Erklärung</h3>
              <FactorExplanation
                explanation={pred.explanation}
                homeName={match.home_team?.name ?? "Heim"}
                awayName={match.away_team?.name ?? "Auswärts"}
              />
            </div>
          )}
        </>
      )}

      {!pred && match.status !== "FINISHED" && (
        <div className="card text-wm-muted text-sm">
          Prognose noch nicht berechnet. Kommt in Kürze.
        </div>
      )}
    </div>
  );
}
