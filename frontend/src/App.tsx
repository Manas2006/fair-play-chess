import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import type { ReviewCase, ReviewDecision, Summary, TimelineMove } from "./types";

const percent = (value = 0, digits = 1) => `${(value * 100).toFixed(digits)}%`;

function Logo() {
  return (
    <div className="brand-mark" aria-hidden="true">
      <span className="brand-knight">♞</span>
      <span className="brand-pulse" />
    </div>
  );
}

function MetricCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <article className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      <div className="metric-detail">{detail}</div>
    </article>
  );
}

function RiskRing({ score }: { score: number }) {
  const degrees = Math.max(0, Math.min(360, score * 360));
  return (
    <div className="risk-ring" style={{ "--risk-degrees": `${degrees}deg` } as React.CSSProperties}>
      <div>
        <strong>{Math.round(score * 100)}</strong>
        <span>risk</span>
      </div>
    </div>
  );
}

function SignalChart({ moves }: { moves: TimelineMove[] }) {
  if (!moves.length) return <div className="empty">No move evidence.</div>;
  const width = 680;
  const height = 170;
  const points = moves
    .map((move, index) => {
      const signal = 0.45 * Number(move.engine_match) + 0.35 * (1 - Math.min(move.cp_loss, 100) / 100) + 0.2 * move.complexity;
      const x = (index / Math.max(moves.length - 1, 1)) * width;
      const y = height - signal * (height - 22) - 8;
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <div className="chart-wrap">
      <div className="chart-axis-label">stronger signal</div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Strongest move evidence signal">
        <defs>
          <linearGradient id="signalFill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#d7f278" stopOpacity="0.42" />
            <stop offset="100%" stopColor="#d7f278" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0.25, 0.5, 0.75].map((tick) => (
          <line key={tick} x1="0" x2={width} y1={height * tick} y2={height * tick} className="chart-grid" />
        ))}
        <polygon points={`0,${height} ${points} ${width},${height}`} fill="url(#signalFill)" />
        <polyline points={points} className="signal-line" />
        {moves.map((move, index) => {
          const signal = 0.45 * Number(move.engine_match) + 0.35 * (1 - Math.min(move.cp_loss, 100) / 100) + 0.2 * move.complexity;
          return (
            <circle
              key={`${move.game_id}-${move.ply}`}
              cx={(index / Math.max(moves.length - 1, 1)) * width}
              cy={height - signal * (height - 22) - 8}
              r={move.engine_match ? 4.5 : 3}
              className={move.engine_match ? "signal-dot match" : "signal-dot"}
            />
          );
        })}
      </svg>
    </div>
  );
}

function Queue({ cases, selected, onSelect }: { cases: ReviewCase[]; selected?: string; onSelect: (item: ReviewCase) => void }) {
  return (
    <section className="queue-panel panel">
      <div className="panel-heading">
        <div>
          <div className="eyebrow">Reviewer budget</div>
          <h2>Priority queue</h2>
        </div>
        <span className="count-pill">{cases.filter((item) => !item.review).length} pending</span>
      </div>
      <div className="queue-columns" aria-hidden="true">
        <span>Rank / account</span><span>Evidence</span><span>Risk</span>
      </div>
      <div className="queue-list">
        {cases.map((item) => (
          <button
            type="button"
            className={`queue-row ${selected === item.account_id ? "selected" : ""}`}
            key={item.account_id}
            onClick={() => onSelect(item)}
          >
            <span className="rank">{String(item.rank).padStart(2, "0")}</span>
            <span className="account-cell">
              <strong>{item.account_id}</strong>
              <small>{item.rating} · {item.dominant_speed} · {item.games_analyzed} games</small>
            </span>
            <span className="evidence-cell">
              <strong>{percent(item.evidence.engine_match_rate, 0)}</strong>
              <small>engine match</small>
            </span>
            <span className={`risk-badge ${item.confidence_band}`}>{percent(item.risk_score, 0)}</span>
            {item.review && <span className={`review-dot ${item.review.decision}`} title={item.review.decision} />}
          </button>
        ))}
      </div>
    </section>
  );
}

function CaseDetail({ item, onDecision }: { item: ReviewCase; onDecision: (decision: ReviewDecision, reason: string) => Promise<void> }) {
  const [reason, setReason] = useState("Evidence pattern merits a second independent review.");
  const [saving, setSaving] = useState(false);
  const submit = async (decision: ReviewDecision) => {
    setSaving(true);
    try { await onDecision(decision, reason); } finally { setSaving(false); }
  };
  return (
    <section className="case-panel panel">
      <div className="case-hero">
        <div>
          <div className="eyebrow">Case {String(item.rank).padStart(2, "0")} · anonymized</div>
          <h2>{item.account_id}</h2>
          <p>Account-level snapshot across {item.moves_analyzed.toLocaleString()} analyzed decisions.</p>
        </div>
        <RiskRing score={item.risk_score} />
      </div>

      <div className="notice">
        <span>Human decision required</span>
        <p>This calibrated score prioritizes review. It is not a finding of misconduct.</p>
      </div>

      <div className="evidence-stats">
        <div><span>Engine match</span><strong>{percent(item.evidence.engine_match_rate)}</strong></div>
        <div><span>Median CP loss</span><strong>{item.evidence.median_cp_loss.toFixed(1)}</strong></div>
        <div><span>Hard-position match</span><strong>{percent(item.evidence.hard_position_match_rate)}</strong></div>
        <div><span>Review state</span><strong className="capitalize">{item.review?.decision ?? "pending"}</strong></div>
      </div>

      <div className="section-title">
        <div><div className="eyebrow">Model evidence</div><h3>Strongest move signals</h3></div>
        <span className="legend"><i /> engine top move</span>
      </div>
      <SignalChart moves={item.evidence.timeline} />

      <div className="move-table-wrap">
        <table className="move-table">
          <thead><tr><th>Game / ply</th><th>Played</th><th>Best</th><th>CP loss</th><th>Time</th></tr></thead>
          <tbody>
            {item.evidence.timeline.slice(0, 6).map((move) => (
              <tr key={`${move.game_id}-${move.ply}`}>
                <td>{move.game_id} <span>#{move.ply}</span></td>
                <td className={move.engine_match ? "move-match" : ""}>{move.move}</td>
                <td>{move.best_move}</td>
                <td>{move.cp_loss.toFixed(1)}</td>
                <td>{move.move_time_s.toFixed(1)}s</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="review-box">
        <label htmlFor="review-note">Review note</label>
        <textarea id="review-note" value={reason} onChange={(event) => setReason(event.target.value)} rows={2} />
        <div className="review-actions">
          <button disabled={saving || reason.length < 3} className="action clear" onClick={() => submit("clear")}>Clear</button>
          <button disabled={saving || reason.length < 3} className="action insufficient" onClick={() => submit("insufficient")}>Need evidence</button>
          <button disabled={saving || reason.length < 3} className="action escalate" onClick={() => submit("escalate")}>Escalate</button>
        </div>
      </div>
    </section>
  );
}

export default function App() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [cases, setCases] = useState<ReviewCase[]>([]);
  const [selectedId, setSelectedId] = useState<string>();
  const [error, setError] = useState<string>();
  const [filter, setFilter] = useState<"all" | "pending" | "reviewed">("all");

  const refresh = async () => {
    const [nextSummary, nextCases] = await Promise.all([api.summary(), api.cases()]);
    setSummary(nextSummary);
    setCases(nextCases);
    setSelectedId((current) => current ?? nextCases[0]?.account_id);
  };

  useEffect(() => { refresh().catch((reason: Error) => setError(reason.message)); }, []);
  const visibleCases = useMemo(() => cases.filter((item) => filter === "all" || (filter === "pending" ? !item.review : !!item.review)), [cases, filter]);
  const selected = cases.find((item) => item.account_id === selectedId) ?? visibleCases[0];

  const decide = async (decision: ReviewDecision, reason: string) => {
    if (!selected) return;
    await api.decide(selected.account_id, decision, reason);
    await refresh();
  };

  if (error) return <main className="center-state"><Logo /><h1>FairPlay Review</h1><p>Could not load the API.</p><code>{error}</code></main>;
  if (!summary) return <main className="center-state"><Logo /><p>Preparing the review queue…</p></main>;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand"><Logo /><div><strong>FairPlay</strong><span>Selective review console</span></div></div>
        <div className="topbar-center"><span className="live-dot" /> Demo model online <i /> Synthetic evidence</div>
        <div className="reviewer"><span>Reviewer</span><strong>MP</strong></div>
      </header>

      <main>
        <div className="page-intro">
          <div><div className="eyebrow">Confidence-conditioned operations</div><h1>Fair-play review</h1><p>Rank accounts by calibrated evidence, then spend a fixed human-review budget where it matters most.</p></div>
          <div className="filters" role="group" aria-label="Filter queue">
            {(["all", "pending", "reviewed"] as const).map((value) => <button key={value} className={filter === value ? "active" : ""} onClick={() => setFilter(value)}>{value}</button>)}
          </div>
        </div>

        <section className="metrics-grid">
          <MetricCard label="Queued for review" value={String(summary.manifest.review_budget ?? cases.length)} detail={`${summary.reviewed} reviewed in this session`} />
          <MetricCard label="PR–AUC" value={(summary.metrics.pr_auc ?? 0).toFixed(3)} detail="synthetic held-out accounts" />
          <MetricCard label="Calibration error" value={percent(summary.metrics.ece_10_bin ?? 0)} detail={`Brier ${(summary.metrics.brier_score ?? 0).toFixed(3)}`} />
          <MetricCard label="Evidence processed" value={`${((summary.manifest.moves ?? 0) / 1000).toFixed(1)}k`} detail={`${summary.manifest.games?.toLocaleString() ?? 0} games · account split`} />
        </section>

        <div className="workspace-grid">
          <Queue cases={visibleCases} selected={selected?.account_id} onSelect={(item) => setSelectedId(item.account_id)} />
          {selected ? <CaseDetail item={selected} onDecision={decide} /> : <section className="panel empty">No cases match this filter.</section>}
        </div>
      </main>

      <footer><span>Portfolio demonstration · synthetic counterfactual labels</span><span>The model routes; humans decide.</span></footer>
    </div>
  );
}
