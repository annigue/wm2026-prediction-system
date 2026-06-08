import { api } from "@/lib/api";
import type { MatchSummary } from "@/types";
import Link from "next/link";

function fmt(iso?: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("de-DE", {
    day: "2-digit", month: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case "FINISHED": return <span className="badge-gray">Abgeschlossen</span>;
    case "LIVE":     return <span className="badge-green animate-pulse">LIVE</span>;
    default:         return <span className="badge-yellow">Geplant</span>;
  }
}

function MiniProbBar({ home, draw, away }: { home: number; draw: number; away: number }) {
  return (
    <div className="flex h-1.5 rounded-full overflow-hidden w-24 gap-px">
      <div className="bg-blue-600 rounded-l-full" style={{ width: `${home * 100}%` }} />
      <div className="bg-gray-500" style={{ width: `${draw * 100}%` }} />
      <div className="bg-red-600 rounded-r-full" style={{ width: `${away * 100}%` }} />
    </div>
  );
}

// Gruppenweise sortieren
function groupMatches(matches: MatchSummary[]) {
  const byGroup: Record<string, MatchSummary[]> = {};
  const ko: MatchSummary[] = [];
  for (const m of matches) {
    if (m.stage === "GROUP_STAGE" && m.group_id) {
      (byGroup[m.group_id] ??= []).push(m);
    } else {
      ko.push(m);
    }
  }
  return { byGroup, ko };
}

export const revalidate = 60;

export default async function MatchesPage() {
  let matches: MatchSummary[] = [];
  try {
    matches = await api.matches();
  } catch {
    // noop
  }

  const { byGroup, ko } = groupMatches(matches);
  const groupIds = Object.keys(byGroup).sort();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Spielplan</h1>

      {matches.length === 0 && (
        <div className="card text-wm-muted text-sm">Spielplan noch nicht geladen.</div>
      )}

      {/* Gruppenphase */}
      {groupIds.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-base font-semibold text-wm-muted uppercase tracking-wider text-xs">Gruppenphase</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {groupIds.map((gid) => (
              <div key={gid} className="card space-y-1">
                <div className="font-bold text-white text-sm mb-2">Gruppe {gid}</div>
                {byGroup[gid].map((m) => (
                  <MatchRow key={m.id} match={m} />
                ))}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* KO-Runden */}
      {ko.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-xs font-semibold text-wm-muted uppercase tracking-wider">KO-Runden</h2>
          <div className="space-y-1">
            {ko.map((m) => (
              <MatchRow key={m.id} match={m} showStage />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function MatchRow({ match: m, showStage = false }: { match: MatchSummary; showStage?: boolean }) {
  const pred = m.prediction;
  const result = m.result;

  return (
    <Link href={`/match/${m.id}`}>
      <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-white/5 transition-colors text-sm">
        {/* Zeit */}
        <span className="text-xs text-wm-muted w-20 shrink-0">{fmt(m.kickoff_utc)}</span>

        {/* Teams */}
        <span className="flex items-center gap-1 flex-1 min-w-0">
          <span>{m.home_team?.flag_emoji ?? "🏳️"}</span>
          <span className={`truncate ${m.status === "FINISHED" ? "text-white" : "text-gray-300"}`}>
            {m.home_team?.name ?? "TBD"}
          </span>
        </span>

        {/* Ergebnis oder Prognose */}
        <span className="w-16 text-center shrink-0">
          {result ? (
            <span className="font-bold font-mono text-white">
              {result.home_goals}:{result.away_goals}
            </span>
          ) : pred ? (
            <MiniProbBar home={pred.prob_home_win} draw={pred.prob_draw} away={pred.prob_away_win} />
          ) : (
            <span className="text-wm-muted text-xs">—</span>
          )}
        </span>

        {/* Teams Away */}
        <span className="flex items-center gap-1 flex-1 min-w-0 justify-end">
          <span className={`truncate ${m.status === "FINISHED" ? "text-white" : "text-gray-300"}`}>
            {m.away_team?.name ?? "TBD"}
          </span>
          <span>{m.away_team?.flag_emoji ?? "🏳️"}</span>
        </span>

        {/* Status */}
        <div className="w-24 text-right shrink-0">
          {showStage && (
            <span className="text-xs text-wm-muted mr-1">
              {m.stage.replace(/_/g, " ")}
            </span>
          )}
          <StatusBadge status={m.status} />
        </div>
      </div>
    </Link>
  );
}
