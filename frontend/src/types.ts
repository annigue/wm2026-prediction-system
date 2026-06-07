// Frontend-Typen — spiegeln die JSON-Shapes der Backend-API (snake_case).
// (Rekonstruiert nach Source-Verlust 2026-06-07; type-only Datei hat kein JS-Output.)

export interface TeamFeatureOut {
  elo_rating: number;
  fifa_ranking?: number | null;
  market_value_millions?: number | null;
  avg_squad_age?: number | null;
  avg_caps_per_player?: number | null;
  form_score?: number | null;
  form_goals_scored_avg?: number | null;
  form_goals_conceded_avg?: number | null;
  snapshot_date?: string | null;
}

export interface EloRatingOut {
  rating: number;
  reason?: string | null;
  created_at?: string | null;
}

export interface TournamentProbsOut {
  group_stage?: number;
  round_of_32?: number | null;
  round_of_16?: number | null;
  quarterfinal?: number | null;
  semifinal?: number | null;
  final?: number | null;
  champion?: number | null;
}

export interface TeamSummary {
  id: string;
  name: string;
  short_name: string;
  flag_emoji?: string | null;
  confederation?: string | null;
  elo_rating?: number | null;
  fifa_ranking?: number | null;
  market_value_millions?: number | null;
  avg_squad_age?: number | null;
  form_score?: number | null;
  champion_probability?: number | null;
}

export interface TeamDetail {
  id: string;
  name: string;
  short_name: string;
  flag_emoji?: string | null;
  confederation?: string | null;
  home_country?: string | null;
  features?: TeamFeatureOut | null;
  elo_history?: EloRatingOut[];
  tournament_probs?: TournamentProbsOut | null;
  group_id?: string | null;
}

export interface PredictionSummary {
  prob_home_win: number;
  prob_draw: number;
  prob_away_win: number;
  xg_home: number;
  xg_away: number;
  model_version?: string | null;
  top_scoreline?: string | null;
}

export interface PredictionDetail extends PredictionSummary {
  predicted_at?: string | null;
  top_scorelines?: { score: string; prob: number }[] | null;
  score_distribution?: Record<string, number> | null;
  explanation?: Record<string, any> | null;
  home_elo_at_prediction?: number | null;
  away_elo_at_prediction?: number | null;
}

export interface ResultOut {
  home_goals: number;
  away_goals: number;
  home_goals_ht?: number | null;
  away_goals_ht?: number | null;
  went_to_extra_time?: boolean;
  went_to_penalties?: boolean;
}

export interface VenueOut {
  name: string;
  city?: string | null;
  country?: string | null;
  altitude_m?: number;
}

export interface MatchSummary {
  id: string;
  stage: string;
  group_id?: string | null;
  home_team?: TeamSummary | null;
  away_team?: TeamSummary | null;
  kickoff_utc?: string | null;
  status?: string | null;
  prediction?: PredictionDetail | null;
  result?: ResultOut | null;
  venue?: VenueOut | null;
}

export interface GroupStandingEntry {
  team_id: string;
  team_name: string;
  flag_emoji?: string | null;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  goals_for: number;
  goals_against: number;
  points: number;
  qualification_probability?: number | null;
  win_group_probability?: number | null;
}

export interface Group {
  id: string;
  name: string;
  teams: GroupStandingEntry[];
}

export interface StageProbs {
  group_stage?: number;
  round_of_32?: number;
  round_of_16?: number;
  quarterfinal?: number;
  semifinal?: number;
  final?: number;
  champion?: number;
}

export interface SimulationResult {
  simulation_id?: number | string | null;
  n_runs?: number;
  model_version?: string;
  simulated_at?: string;
  champion_probabilities: Record<string, number>;
  stage_probabilities: Record<string, StageProbs>;
}

export interface MiniMatch {
  id: string;
  stage: string;
  group_id?: string | null;
  kickoff_utc?: string | null;
  status?: string | null;
  home_team?: string | null;
  home_flag?: string | null;
  away_team?: string | null;
  away_flag?: string | null;
  result?: string | null;
}

// Alias-Namen (Original-Frontend nutzte teils Namen ohne "Out"-Suffix)
export type TournamentProbs = TournamentProbsOut;
export type TeamFeature = TeamFeatureOut;
export type EloRating = EloRatingOut;
export type MatchResult = ResultOut;
export type Venue = VenueOut;

export interface FavoriteEntry {
  team_id: string;
  name?: string | null;
  flag?: string | null;
  champion_prob: number;
}

export interface TournamentStatus {
  matches_played: number;
  matches_total: number;
  stage: string;
}

export interface DashboardData {
  top_favorites?: FavoriteEntry[];
  tournament_status?: TournamentStatus;
  next_matches: MiniMatch[];
  recent_results: MiniMatch[];
  last_simulation?: string | null;
}
