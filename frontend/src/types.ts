export type ReviewDecision = "clear" | "insufficient" | "escalate";

export interface TimelineMove {
  game_id: string;
  ply: number;
  move: string;
  move_san: string;
  best_move: string;
  best_move_san: string;
  fen_before: string;
  fen_after: string;
  eval_cp: number;
  player_color: "white" | "black";
  cp_loss: number;
  complexity: number;
  move_time_s: number;
  engine_match: boolean;
  injected: boolean;
}

export interface CaseEvidence {
  engine_match_rate: number;
  median_cp_loss: number;
  hard_position_match_rate: number;
  timeline: TimelineMove[];
}

export interface ReviewRecord {
  account_id: string;
  decision: ReviewDecision;
  reason: string;
  reviewer: string;
  reviewed_at: string;
}

export interface ReviewCase {
  account_id: string;
  rank: number;
  risk_score: number;
  confidence_band: string;
  games_analyzed: number;
  moves_analyzed: number;
  rating: number;
  dominant_speed: string;
  synthetic_ground_truth: boolean;
  assistance_rate: number;
  evidence: CaseEvidence;
  review: ReviewRecord | null;
}

export interface Summary {
  manifest: {
    accounts?: number;
    games?: number;
    moves?: number;
    review_budget?: number;
    data_mode?: string;
  };
  metrics: {
    pr_auc?: number;
    brier_score?: number;
    ece_10_bin?: number;
    warning?: string;
  };
  reviewed: number;
  decision_counts: Record<ReviewDecision, number>;
}
