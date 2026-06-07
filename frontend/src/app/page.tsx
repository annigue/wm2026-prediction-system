import { api } from "@/lib/api";
import type { DashboardData, SimulationResult } from "@/types";
import Link from "next/link";

function fmt(iso?: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("de-DE", {
    weekday: "short", day: "2-digit", month: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

function ProbBar({ prob, color = "bg-wm-gold" }: { prob: number; color?: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-2 rounded-full bg-gray-700 overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${Math.min(prob * 600, 100)}%` }} />
      </div>
      <span className="text-wm-gold font-bold text-sm w-10 text-right">
        {(prob * 100).toFixed(1)}%
      </span>
    </div>
  );
}

export default async function DashboardPage() {
  let data: DashboardData | null = null;
  let sim: SimulationResult | null = null;

  try {
    [data, sim] = await Promise.all([
      api.dashboard().catch(() => null),
      api.simulation().catch(() => null),
    ]);
    if (sim?.simulation_id == null) sim = null;
  } catch {
    // Backend nicht erreichbar
  }

  const nextMatches = data?.next_matches ?? [];
  const recentResults = data?.recent_results ?? [];
  const status = data?.tournament_status;

  // Champion-Wahrscheinlichkeiten aus Simulation (top 10)
  const favorites = sim
    ? Object.entries(sim.champion_probabilities)
        .sort(([, a], [, b]) => (b as number) - (a as number))
        .slice(0, 10)
    : data?.top_favorites?.map((f) => [f.team_id, f.champion_prob] as [string, number]) ?? [];

  // Teams für Flag-Lookup
  const teams = await api.teams().catch(() => []);
  const teamMap = Object.fromEntries(teams.map((t) => [t.id, t]));

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-white">🏆 WM 2026</h1>
        <p className="text-wm-muted mt-1 text-sm">
          Elo · Poisson · 100.000 Monte-Carlo-Simulationen · Erklärbar
        </p>
      </div>

      {/* Turnierstatus */}
      {status && (
        <div className="card grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-2xl font-bold text-white">
              {status.matches_played}
            </div>
            <div className="text-xs text-wm-muted">Gespielte Spiele</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-white">
              {status.matches_total - status.matches_played}
            </div>
            <div className="text-xs text-wm-muted">Verbleibend</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-white">
              {status.stage.replace(/_/g, " ")}
            </div>
            <div className="text-xs text-wm-muted">Phase</div>
          </div>
        </div>
      )}

      {!data && (
        <div className="card border-yellow-800 bg-yellow-900/20 text-yellow-400 text-sm">
          Backend nicht erreichbar.{" "}
          <code className="text-xs">docker-compose up</code> starten.
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Titelchancen */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">Titelchancen</h2>
            <Link href="/bracket" className="text-xs text-wm-muted hover:text-white">
              Alle anzeigen →
            </Link>
          </div>
          <div className="space-y-1.5">
            {favorites.length === 0 ? (
              <div className="card text-wm-muted text-sm">
                Noch keine Simulation. "🎲 Simulieren" klicken.
              </div>
            ) : (
              favorites.map(([teamId, prob], i) => {
                const team = teamMap[teamId as string];
                return (
                  <Link key={teamId} href={`/team/${teamId}`}>
                    <div className="card flex items-center gap-3 hover:border-gray-500 transition-colors cursor-pointer py-2">
                      <span className="text-wm-muted text-xs w-4">{i + 1}</span>
                      <span className="text-xl">{team?.flag_emoji ?? "🏳️"}</span>
                      <span className="flex-1 text-sm font-medium text-white">
                        {team?.name ?? (teamId as string)}
                      </span>
                      <ProbBar prob={prob as number} />
                    </div>
                  </Link>
                );
              })
            )}
          </div>
          {sim && (
            <p className="text-xs text-wm-muted">
              Basis: {sim.n_runs?.toLocaleString("de-DE")} Simulationen ·{" "}
              {new Date(sim.simulated_at).toLocaleDateString("de-DE")}
            </p>
          )}
        </section>

        <div className="space-y-6">
          {/* Nächste Spiele */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold text-white">Nächste Spiele</h2>
              <Link href="/matches" className="text-xs text-wm-muted hover:text-white">
                Alle →
              </Link>
            </div>
            <div className="space-y-2">
              {nextMatches.length === 0 ? (
                <div className="card text-wm-muted text-sm">Kein Spielplan geladen.</div>
              ) : (
                nextMatches.map((m) => (
                  <Link key={m.id} href={`/match/${m.id}`}>
                    <div className="card flex items-center justify-between gap-2 hover:border-gray-500 transition-colors cursor-pointer py-2">
                      <span className="text-xs text-wm-muted w-24 shrink-0">
                        {fmt(m.kickoff_utc)}
                      </span>
                      <span className="text-sm font-medium flex-1 text-center truncate">
                        {m.home_team}{" "}
                        <span className="text-wm-muted">vs</span>{" "}
                        {m.away_team}
                      </span>
                    </div>
                  </Link>
                ))
              )}
            </div>
          </section>

          {/* Letzte Ergebnisse */}
          {recentResults.length > 0 && (
            <section>
              <h2 className="text-lg font-semibold text-white mb-3">Letzte Ergebnisse</h2>
              <div className="space-y-2">
                {recentResults.map((m) => (
                  <Link key={m.id} href={`/match/${m.id}`}>
                    <div className="card flex items-center justify-between hover:border-gray-500 transition-colors cursor-pointer py-2">
                      <span className="text-sm">{m.home_team}</span>
                      <span className="font-bold text-white px-3 font-mono">
                        {m.result ?? "—"}
                      </span>
                      <span className="text-sm">{m.away_team}</span>
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
