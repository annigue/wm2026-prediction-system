import { api } from "@/lib/api";
import { ProbabilityBar } from "@/components/ui/ProbabilityBar";
import Link from "next/link";
import type { TeamDetail, TournamentProbs } from "@/types";

function pct(n: number | null | undefined, decimals = 1) {
  if (n == null) return "—";
  return `${(n * 100).toFixed(decimals)}%`;
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card text-center">
      <div className="text-xs text-wm-muted mb-1">{label}</div>
      <div className="font-bold text-white text-lg">{value}</div>
      {sub && <div className="text-xs text-wm-muted mt-0.5">{sub}</div>}
    </div>
  );
}

function StageRow({ label, prob, highlight }: { label: string; prob: number | undefined; highlight?: boolean }) {
  if (prob == null) return null;
  return (
    <div className={`flex items-center gap-3 py-1.5 border-b border-wm-border/30 last:border-0 ${highlight ? "text-white" : "text-gray-400"}`}>
      <span className="text-sm w-32">{label}</span>
      <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${highlight ? "bg-wm-gold" : "bg-gray-500"}`}
          style={{ width: `${Math.min(prob * 100, 100)}%` }}
        />
      </div>
      <span className={`text-sm font-mono w-12 text-right ${highlight ? "text-wm-gold font-bold" : ""}`}>
        {pct(prob)}
      </span>
    </div>
  );
}

export default async function TeamPage({ params }: { params: { id: string } }) {
  let team: TeamDetail | null = null;
  let simProbs: TournamentProbs | null = null;
  let teamMatches: any[] = [];

  try {
    [team, teamMatches] = await Promise.all([
      api.team(params.id),
      api.matches({ team_id: params.id }),
    ]);
  } catch {
    return <div className="card text-red-400">Team nicht gefunden: {params.id}</div>;
  }

  // Simulationsdaten aus /tournament/simulate holen
  try {
    const sim = await api.simulation();
    if (sim?.simulation_id != null && sim.stage_probabilities?.[params.id]) {
      simProbs = sim.stage_probabilities[params.id];
    }
  } catch {
    // Simulation noch nicht vorhanden
  }

  const f = team.features;
  const groupId = team.group_id;

  // Nächstes + letztes Spiel finden
  const upcoming = teamMatches.filter((m) => m.status === "SCHEDULED").slice(0, 3);
  const played   = teamMatches.filter((m) => m.status === "FINISHED").slice(-3).reverse();

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Breadcrumb */}
      <div className="text-xs text-wm-muted">
        {groupId && <Link href="/groups" className="hover:text-white">← Gruppen</Link>}
      </div>

      {/* Team-Header */}
      <div className="card flex items-center gap-6">
        <div className="text-7xl">{team.flag_emoji ?? "🏳️"}</div>
        <div className="flex-1">
          <h1 className="text-3xl font-bold text-white">{team.name}</h1>
          <div className="flex gap-3 mt-1 text-sm text-wm-muted flex-wrap">
            {team.confederation && <span>{team.confederation}</span>}
            {team.home_country && <span>· {team.home_country}</span>}
            {groupId && (
              <span>
                ·{" "}
                <Link href="/groups" className="hover:text-white">
                  Gruppe {groupId}
                </Link>
              </span>
            )}
          </div>
        </div>
        {simProbs?.champion != null && (
          <div className="text-center">
            <div className="text-3xl font-black text-wm-gold">{pct(simProbs.champion)}</div>
            <div className="text-xs text-wm-muted">Titelchance</div>
          </div>
        )}
      </div>

      {/* Kennzahlen */}
      {f && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard label="Elo-Rating" value={f.elo_rating ? Math.round(f.elo_rating).toString() : "—"} />
          <StatCard label="FIFA-Ranking" value={f.fifa_ranking ? `#${f.fifa_ranking}` : "—"} />
          <StatCard
            label="Marktwert"
            value={f.market_value_millions ? `${f.market_value_millions.toFixed(0)} M€` : "—"}
          />
          <StatCard
            label="Ø Alter"
            value={f.avg_squad_age ? `${f.avg_squad_age.toFixed(1)} J` : "—"}
            sub={f.avg_caps_per_player ? `Ø ${f.avg_caps_per_player.toFixed(0)} Caps` : undefined}
          />
        </div>
      )}

      {/* Form */}
      {f?.form_score != null && (
        <div className="card space-y-2">
          <h3 className="text-sm font-semibold text-white">Aktuelle Form</h3>
          <div className="flex items-center gap-3">
            <div className="flex-1 h-3 bg-gray-700 rounded-full overflow-hidden relative">
              {/* Mittelmarkierung */}
              <div className="absolute left-1/2 top-0 bottom-0 w-px bg-gray-500" />
              {/* Form-Balken (von Mitte) */}
              <div
                className={`absolute top-0 bottom-0 rounded-full transition-all ${
                  f.form_score >= 0 ? "bg-green-500 left-1/2" : "bg-red-500 right-1/2"
                }`}
                style={{ width: `${Math.abs(f.form_score) * 50}%` }}
              />
            </div>
            <span className={`font-bold w-12 text-right ${f.form_score > 0.3 ? "text-green-400" : f.form_score < -0.3 ? "text-red-400" : "text-gray-400"}`}>
              {f.form_score > 0 ? "+" : ""}{(f.form_score * 100).toFixed(0)}
            </span>
          </div>
          <div className="flex justify-between text-xs text-wm-muted">
            <span>Schlechte Form</span>
            <span>Neutral</span>
            <span>Sehr gut</span>
          </div>
        </div>
      )}

      {/* Turnier-Prognosen */}
      {simProbs && (
        <div className="card space-y-1">
          <h3 className="text-sm font-semibold text-white mb-3">
            Turnier-Prognosen
            <span className="text-xs text-wm-muted font-normal ml-2">(100.000 Monte-Carlo-Simulationen)</span>
          </h3>
          <StageRow label="Round of 32" prob={simProbs.round_of_32} />
          <StageRow label="Round of 16" prob={simProbs.round_of_16} />
          <StageRow label="Viertelfinale" prob={simProbs.quarterfinal} />
          <StageRow label="Halbfinale" prob={simProbs.semifinal} />
          <StageRow label="Finale" prob={simProbs.final} />
          <StageRow label="🏆 Weltmeister" prob={simProbs.champion} highlight />
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Nächste Spiele */}
        {upcoming.length > 0 && (
          <div className="card space-y-2">
            <h3 className="text-sm font-semibold text-white">Nächste Spiele</h3>
            {upcoming.map((m) => {
              const isHome = m.home_team?.id === params.id;
              const opp = isHome ? m.away_team : m.home_team;
              const pred = m.prediction;
              const myProb = pred ? (isHome ? pred.prob_home_win : pred.prob_away_win) : null;
              return (
                <Link key={m.id} href={`/match/${m.id}`} className="block">
                  <div className="flex items-center gap-2 p-2 rounded-lg hover:bg-white/5 transition-colors">
                    <span className="text-lg">{opp?.flag_emoji ?? "🏳️"}</span>
                    <div className="flex-1">
                      <div className="text-sm font-medium">
                        {isHome ? "vs" : "bei"} {opp?.name ?? "TBD"}
                      </div>
                      <div className="text-xs text-wm-muted">
                        {m.kickoff_utc
                          ? new Date(m.kickoff_utc).toLocaleDateString("de-DE", {
                              weekday: "short", day: "2-digit", month: "2-digit",
                            })
                          : "—"}
                      </div>
                    </div>
                    {myProb != null && (
                      <span className={`text-sm font-bold ${myProb > 0.5 ? "text-green-400" : myProb > 0.35 ? "text-yellow-400" : "text-red-400"}`}>
                        {pct(myProb)}
                      </span>
                    )}
                  </div>
                </Link>
              );
            })}
          </div>
        )}

        {/* Gespielte Spiele */}
        {played.length > 0 && (
          <div className="card space-y-2">
            <h3 className="text-sm font-semibold text-white">Zuletzt gespielt</h3>
            {played.map((m) => {
              const isHome = m.home_team?.id === params.id;
              const opp = isHome ? m.away_team : m.home_team;
              const r = m.result;
              const myGoals = r ? (isHome ? r.home_goals : r.away_goals) : null;
              const oppGoals = r ? (isHome ? r.away_goals : r.home_goals) : null;
              const won = myGoals != null && oppGoals != null && myGoals > oppGoals;
              const draw = myGoals != null && oppGoals != null && myGoals === oppGoals;
              return (
                <Link key={m.id} href={`/match/${m.id}`} className="block">
                  <div className="flex items-center gap-2 p-2 rounded-lg hover:bg-white/5 transition-colors">
                    <span className={`text-xs font-bold w-5 ${won ? "text-green-400" : draw ? "text-yellow-400" : "text-red-400"}`}>
                      {won ? "S" : draw ? "U" : "N"}
                    </span>
                    <span className="text-lg">{opp?.flag_emoji ?? "🏳️"}</span>
                    <span className="flex-1 text-sm">{opp?.name ?? "TBD"}</span>
                    {r && (
                      <span className="font-mono text-sm text-white">
                        {isHome ? `${r.home_goals}:${r.away_goals}` : `${r.away_goals}:${r.home_goals}`}
                      </span>
                    )}
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>

      {/* Elo-Verlauf */}
      {team.elo_history && team.elo_history.length > 1 && (
        <div className="card space-y-2">
          <h3 className="text-sm font-semibold text-white">Elo-Verlauf</h3>
          <div className="space-y-1">
            {team.elo_history.slice(0, 10).map((e, i) => (
              <div key={i} className="flex justify-between text-xs text-wm-muted">
                <span>{e.reason ?? "Update"}</span>
                <span className="font-mono text-white">{Math.round(e.rating)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
