import { api } from "@/lib/api";
import type { Group, SimulationResult } from "@/types";
import Link from "next/link";

function pct(n: number | null | undefined) {
  if (n == null) return null;
  return `${(n * 100).toFixed(0)}%`;
}

export default async function GroupsPage() {
  let groups: Group[] = [];
  let sim: SimulationResult | null = null;

  try {
    [groups, sim] = await Promise.all([
      api.groups(),
      api.simulation().catch(() => null),
    ]);
    if (sim?.simulation_id == null) sim = null;
  } catch {
    // noop
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Gruppenphase</h1>
        {sim && (
          <p className="text-wm-muted text-sm mt-1">
            Qualifikations-% aus {sim.n_runs?.toLocaleString("de-DE")} Monte-Carlo-Simulationen
          </p>
        )}
      </div>

      {groups.length === 0 && (
        <div className="card text-wm-muted text-sm">Noch keine Gruppen geladen.</div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {groups.map((group) => (
          <div key={group.id} className="card space-y-3">
            <h2 className="font-bold text-white text-sm border-b border-wm-border pb-2">
              Gruppe {group.id}
            </h2>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-wm-muted">
                  <th className="text-left pb-1.5">Team</th>
                  <th className="text-right pb-1.5">Sp</th>
                  <th className="text-right pb-1.5">Pkt</th>
                  <th className="text-right pb-1.5">TD</th>
                  {sim && <th className="text-right pb-1.5 text-wm-gold/70">R32</th>}
                </tr>
              </thead>
              <tbody>
                {group.teams.map((entry, i) => {
                  const stageP = sim?.stage_probabilities?.[entry.team_id];
                  const qualProb = stageP?.round_of_32;
                  const isQualified = i < 2; // Top 2 direkt qualifiziert (vereinfacht)

                  return (
                    <tr
                      key={entry.team_id}
                      className={`border-b border-wm-border/40 last:border-0 ${
                        i < 2 ? "text-white" : "text-wm-muted"
                      }`}
                    >
                      <td className="py-1.5">
                        <Link
                          href={`/team/${entry.team_id}`}
                          className="flex items-center gap-1.5 hover:text-white transition-colors"
                        >
                          <span>{entry.flag_emoji ?? "🏳️"}</span>
                          <span className="truncate max-w-[90px]">{entry.team_name}</span>
                        </Link>
                      </td>
                      <td className="text-right">{entry.played}</td>
                      <td className="text-right font-bold">{entry.points}</td>
                      <td className="text-right">
                        {entry.goals_for - entry.goals_against > 0
                          ? `+${entry.goals_for - entry.goals_against}`
                          : entry.goals_for - entry.goals_against}
                      </td>
                      {sim && (
                        <td className="text-right">
                          {qualProb != null ? (
                            <span
                              className={`font-mono ${
                                qualProb > 0.7
                                  ? "text-green-400"
                                  : qualProb > 0.4
                                    ? "text-yellow-400"
                                    : "text-red-400"
                              }`}
                            >
                              {pct(qualProb)}
                            </span>
                          ) : (
                            <span className="text-wm-muted">—</span>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ))}
      </div>

      {sim && (
        <p className="text-xs text-wm-muted text-center">
          R32 = Qualifikation für Round of 32 (Top 2 jeder Gruppe + 8 beste Drittplatzierte)
        </p>
      )}
    </div>
  );
}
