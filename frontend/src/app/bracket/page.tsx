import { api } from "@/lib/api";
import Link from "next/link";

function pct(n: number | undefined) {
  if (n == null) return "—";
  return `${(n * 100).toFixed(1)}%`;
}

function StageBar({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-16 h-1.5 rounded-full bg-gray-700 overflow-hidden">
        <div className="h-full bg-wm-gold rounded-full" style={{ width: `${Math.min(value * 500, 100)}%` }} />
      </div>
      <span className="text-wm-gold font-bold text-xs w-10">{pct(value)}</span>
    </div>
  );
}

export default async function BracketPage() {
  let sim = null;
  let teams: any[] = [];

  try {
    const [simRaw, teamsRaw] = await Promise.all([api.simulation(), api.teams()]);
    if (simRaw?.simulation_id != null) sim = simRaw;
    teams = teamsRaw ?? [];
  } catch {
    // noop
  }

  // Team-Lookup für Flaggen
  const teamMap = Object.fromEntries(teams.map((t: any) => [t.id, t]));

  const sorted = sim
    ? Object.entries(sim.champion_probabilities)
        .sort(([, a], [, b]) => (b as number) - (a as number))
    : [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Turnierbaum & Titelchancen</h1>
        {sim ? (
          <p className="text-wm-muted text-sm mt-1">
            {sim.n_runs?.toLocaleString("de-DE")} Monte-Carlo-Simulationen ·
            Modell {sim.model_version} ·{" "}
            {new Date(sim.simulated_at).toLocaleString("de-DE", {
              day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
            })}
          </p>
        ) : (
          <p className="text-wm-muted text-sm mt-1">
            Noch keine Simulation. Klick auf "🎲 Simulieren" in der Navigationsleiste.
          </p>
        )}
      </div>

      {sorted.length > 0 && (
        <>
          {/* Top 8 Titelkandidaten — hervorgehoben */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {sorted.slice(0, 8).map(([teamId, prob], i) => {
              const team = teamMap[teamId];
              const stageP = sim?.stage_probabilities?.[teamId];
              return (
                <Link key={teamId} href={`/team/${teamId}`}>
                  <div className="card hover:border-gray-500 transition-colors text-center space-y-1.5 cursor-pointer">
                    <div className="text-2xl">{team?.flag_emoji ?? "🏳️"}</div>
                    <div className="font-medium text-sm truncate">{team?.name ?? teamId}</div>
                    <div className="text-wm-gold font-bold text-lg">{pct(prob as number)}</div>
                    <div className="text-xs text-wm-muted">Titelchance</div>
                    {stageP && (
                      <div className="text-xs text-wm-muted space-y-0.5 pt-1 border-t border-wm-border">
                        <div>Finale: {pct(stageP.final)}</div>
                        <div>HF: {pct(stageP.semifinal)}</div>
                      </div>
                    )}
                  </div>
                </Link>
              );
            })}
          </div>

          {/* Vollständige Tabelle aller 48 Teams */}
          <div className="card space-y-1">
            <h2 className="font-semibold text-white mb-3">Alle Teams — Rundenwahrscheinlichkeiten</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-wm-muted border-b border-wm-border">
                    <th className="text-left py-1.5 w-6">#</th>
                    <th className="text-left py-1.5">Team</th>
                    <th className="text-right py-1.5 px-2">R32</th>
                    <th className="text-right py-1.5 px-2">R16</th>
                    <th className="text-right py-1.5 px-2">VF</th>
                    <th className="text-right py-1.5 px-2">HF</th>
                    <th className="text-right py-1.5 px-2">Finale</th>
                    <th className="text-left py-1.5 pl-3">Titel</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map(([teamId, prob], i) => {
                    const team = teamMap[teamId];
                    const s = sim?.stage_probabilities?.[teamId];
                    return (
                      <tr key={teamId} className="border-b border-wm-border/30 hover:bg-white/5">
                        <td className="py-1.5 text-wm-muted pr-2">{i + 1}</td>
                        <td className="py-1.5">
                          <Link href={`/team/${teamId}`} className="flex items-center gap-1.5 hover:text-white">
                            <span>{team?.flag_emoji ?? "🏳️"}</span>
                            <span className={i < 8 ? "text-white font-medium" : "text-gray-400"}>
                              {team?.name ?? teamId}
                            </span>
                          </Link>
                        </td>
                        <td className="py-1.5 px-2 text-right text-gray-400">{s ? pct(s.round_of_32) : "—"}</td>
                        <td className="py-1.5 px-2 text-right text-gray-400">{s ? pct(s.round_of_16) : "—"}</td>
                        <td className="py-1.5 px-2 text-right text-gray-400">{s ? pct(s.quarterfinal) : "—"}</td>
                        <td className="py-1.5 px-2 text-right text-gray-400">{s ? pct(s.semifinal) : "—"}</td>
                        <td className="py-1.5 px-2 text-right text-gray-300">{s ? pct(s.final) : "—"}</td>
                        <td className="py-1.5 pl-3">
                          <StageBar value={prob as number} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
