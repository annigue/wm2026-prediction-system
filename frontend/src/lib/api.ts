import type {
  TeamSummary, TeamDetail, Group, MatchSummary,
  SimulationResult, DashboardData,
} from "@/types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API = `${BASE}/api/v1`;

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  dashboard: () => get<DashboardData>("/dashboard"),

  teams: () => get<{ teams: TeamSummary[] }>("/teams").then((r) => r.teams),
  team: (id: string) => get<TeamDetail>(`/teams/${id}`),

  groups: () => get<{ groups: Group[] }>("/groups").then((r) => r.groups),

  matches: (params?: {
    stage?: string;
    group_id?: string;
    team_id?: string;
    status?: string;
  }) => {
    const q = new URLSearchParams(
      Object.entries(params ?? {}).filter(([, v]) => v != null) as [string, string][]
    ).toString();
    return get<{ matches: MatchSummary[] }>(`/matches${q ? `?${q}` : ""}`).then((r) => r.matches);
  },

  match: (id: string) => get<MatchSummary>(`/matches/${id}`),

  bets: (matchId: string) => get<any>(`/matches/${matchId}/bets`),
  tip:  (matchId: string) => get<any>(`/matches/${matchId}/tip`),
  projection: () => get<any>("/tournament/projection"),

  simulation: () => get<SimulationResult>("/tournament/simulate"),
  championProbs: () =>
    get<{ champion_probabilities: Record<string, number> }>("/tournament/champion-probabilities"),

  postResult: (matchId: string, body: {
    home_goals: number;
    away_goals: number;
    home_goals_ht?: number;
    away_goals_ht?: number;
    went_to_extra_time?: boolean;
    went_to_penalties?: boolean;
  }, adminToken: string) =>
    fetch(`${API}/matches/${matchId}/result`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${adminToken}`,
      },
      body: JSON.stringify(body),
    }).then((r) => r.json()),
};
