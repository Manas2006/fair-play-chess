import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api } from "./api";
import type { ReviewCase, ReviewDecision, Summary, TimelineMove } from "./types";

const percent = (value = 0, digits = 1) => `${(value * 100).toFixed(digits)}%`;
const PIECES: Record<string, string> = {
  K: "♔", Q: "♕", R: "♖", B: "♗", N: "♘", P: "♙",
  k: "♚", q: "♛", r: "♜", b: "♝", n: "♞", p: "♟"
};

type IconName = "queue" | "chart" | "search" | "chevron" | "shield" | "check" | "flag" | "info";

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, ReactNode> = {
    queue: <><path d="M5 6h14M5 12h14M5 18h14"/><circle cx="2.5" cy="6" r=".5"/><circle cx="2.5" cy="12" r=".5"/><circle cx="2.5" cy="18" r=".5"/></>,
    chart: <><path d="M4 19V9m6 10V5m6 14v-7m4 7V3"/></>,
    search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 4 4"/></>,
    chevron: <path d="m9 18 6-6-6-6"/>,
    shield: <path d="M12 2.5 20 6v5.5c0 5-3.4 8.6-8 10-4.6-1.4-8-5-8-10V6l8-3.5Z"/>,
    check: <path d="m5 12 4.2 4.2L19 6.5"/>,
    flag: <><path d="M5 21V4"/><path d="M5 5h11l-2 3 2 3H5"/></>,
    info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></>
  };
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

function BrandMark() {
  return (
    <div className="brand-mark" aria-hidden="true">
      <svg viewBox="0 0 24 24" width="26" height="26" fill="#fff">
        <rect x="7" y="3.5" width="2.4" height="4.5"/>
        <rect x="10.8" y="3.5" width="2.4" height="4.5"/>
        <rect x="14.6" y="3.5" width="2.4" height="4.5"/>
        <rect x="7" y="6.5" width="10" height="2.5"/>
        <rect x="8.5" y="9" width="7" height="8.5"/>
        <rect x="6.5" y="17" width="11" height="2"/>
        <rect x="5" y="19" width="14" height="2"/>
      </svg>
    </div>
  );
}

function EvaluationBar({ centipawns }: { centipawns: number }) {
  const normalized = 1 / (1 + Math.exp(-centipawns / 230));
  const whiteHeight = Math.max(7, Math.min(93, normalized * 100));
  const label = `${centipawns >= 0 ? "+" : "−"}${Math.abs(centipawns / 100).toFixed(1)}`;
  return (
    <div className="eval-wrap" aria-label={`Position evaluation ${label}`}>
      <div className="eval-bar">
        <div className="eval-white" style={{ height: `${whiteHeight}%` }} />
        <span className={whiteHeight > 56 ? "on-white" : "on-black"}>{label}</span>
      </div>
      <small>Eval</small>
    </div>
  );
}

function parseFen(fen: string): (string | null)[][] {
  const placement = (fen || "8/8/8/8/8/8/8/8").split(" ")[0];
  return placement.split("/").map((rank) => {
    const squares: (string | null)[] = [];
    for (const token of rank) {
      if (/\d/.test(token)) squares.push(...Array(Number(token)).fill(null));
      else squares.push(token);
    }
    return squares;
  });
}

function Chessboard({ move }: { move: TimelineMove }) {
  const board = parseFen(move.fen_after || move.fen_before);
  const from = move.move.slice(0, 2);
  const to = move.move.slice(2, 4);
  return (
    <div className="board-area">
      <EvaluationBar centipawns={move.eval_cp} />
      <div className="chessboard" role="img" aria-label={`Position after ${move.move_san || move.move}`}>
        {board.flatMap((rank, rankIndex) => rank.map((piece, fileIndex) => {
          const square = `${String.fromCharCode(97 + fileIndex)}${8 - rankIndex}`;
          const dark = (rankIndex + fileIndex) % 2 === 1;
          const highlighted = square === from || square === to;
          return (
            <div key={square} className={`square ${dark ? "dark" : "light"} ${highlighted ? "highlighted" : ""}`}>
              {piece && <span className={`piece ${piece === piece.toUpperCase() ? "white-piece" : "black-piece"}`}>{PIECES[piece]}</span>}
              {fileIndex === 0 && <small className="rank-label">{8 - rankIndex}</small>}
              {rankIndex === 7 && <small className="file-label">{String.fromCharCode(97 + fileIndex)}</small>}
            </div>
          );
        }))}
      </div>
    </div>
  );
}

function leadingSignal(item: ReviewCase) {
  const signals = [
    { value: item.evidence.engine_match_rate, label: "High engine agreement" },
    { value: item.evidence.hard_position_match_rate, label: "Strong in hard positions" },
    { value: Math.max(0, 1 - item.evidence.median_cp_loss / 35), label: "Unusually low move loss" }
  ];
  return signals.sort((a, b) => b.value - a.value)[0].label;
}

function signalReasons(item: ReviewCase) {
  return [
    {
      label: "Engine agreement",
      value: percent(item.evidence.engine_match_rate),
      detail: "Share of analyzed moves matching a reference engine choice.",
      strength: item.evidence.engine_match_rate
    },
    {
      label: "Move consistency",
      value: `${item.evidence.median_cp_loss.toFixed(1)} CP`,
      detail: "Median loss versus the reference move; lower is stronger.",
      strength: Math.max(0, 1 - item.evidence.median_cp_loss / 35)
    },
    {
      label: "Hard-position agreement",
      value: percent(item.evidence.hard_position_match_rate),
      detail: "Reference matches when the position has difficult alternatives.",
      strength: item.evidence.hard_position_match_rate
    }
  ].sort((a, b) => b.strength - a.strength);
}

function Queue({ cases, selected, onSelect }: { cases: ReviewCase[]; selected?: string; onSelect: (item: ReviewCase) => void }) {
  return (
    <div className="case-list" aria-label="Review cases">
      {cases.map((item) => (
        <button type="button" className={`case-row ${selected === item.account_id ? "selected" : ""}`} key={item.account_id} onClick={() => onSelect(item)}>
          <span className="case-rank">#{item.rank}</span>
          <span className="case-copy">
            <span><strong>{item.account_id}</strong><time>{item.dominant_speed}</time></span>
            <span className="case-signal">{leadingSignal(item)}</span>
            <span className="case-meta">{item.rating} rating · {item.games_analyzed} games</span>
          </span>
          <span className="risk-stack"><strong>{Math.round(item.risk_score * 100)}</strong><small>score</small></span>
          <span className={`status-orb ${item.review?.decision ?? "pending"}`} />
          <Icon name="chevron" size={15}/>
        </button>
      ))}
    </div>
  );
}

function EvidenceBrowser({ moves, real }: { moves: TimelineMove[]; real?: boolean }) {
  const [index, setIndex] = useState(0);
  useEffect(() => setIndex(0), [moves]);
  const move = moves[Math.min(index, Math.max(0, moves.length - 1))];
  if (!move) return <div className="empty-state">No position evidence is available.</div>;
  const choose = (next: number) => setIndex(Math.max(0, Math.min(moves.length - 1, next)));
  const matched = move.engine_match;
  return (
    <section className="evidence-browser">
      <div className="analysis-layout">
        <div className="board-column">
          <div className="board-context"><span>Evidence position {index + 1}</span><strong>{move.game_id} · move {Math.ceil(move.ply / 2)}</strong></div>
          <Chessboard move={move} />
          <div className="board-caption"><Icon name="info" size={15}/><span>Yellow squares show the played move. Positive evaluation favors White.</span></div>
        </div>

        <div className="coach-panel">
          <header className="coach-header">
            <div className="coach-avatar">♞</div>
            <div><span>Evidence guide</span><strong>{matched ? "This move matched the reference" : "This move differed from the reference"}</strong></div>
          </header>

          <div className={`classification ${matched ? "matched" : "different"}`}>
            <span>{matched ? "✓" : "!"}</span>
            <div><strong>{matched ? "Reference match" : "Different move"}</strong><small>{matched ? "One supporting signal—never proof on its own" : "A useful comparison point for the reviewer"}</small></div>
          </div>

          <div className="move-comparison">
            <div><span>Played</span><strong>{move.move_san || move.move}</strong><code>{move.move}</code></div>
            <div className="comparison-arrow">→</div>
            <div><span>Reference</span><strong>{move.best_move_san || move.best_move}</strong><code>{move.best_move}</code></div>
          </div>

          <div className="signal-details">
            <div><span>Move loss</span><strong>{move.cp_loss.toFixed(1)} <small>CP</small></strong></div>
            <div><span>Think time</span><strong>{move.move_time_s.toFixed(1)}<small>s</small></strong></div>
            <div><span>Complexity</span><strong>{percent(move.complexity, 0)}</strong></div>
          </div>

          <div className="move-list-wrap">
            <div className="move-list-title"><span>Strongest evidence positions</span><small>ranked by signal</small></div>
            <div className="position-strip">
              {moves.slice(0, 12).map((candidate, candidateIndex) => (
                <button key={`${candidate.game_id}-${candidate.ply}`} className={candidateIndex === index ? "active" : ""} onClick={() => choose(candidateIndex)} aria-label={`Open ${candidate.game_id} ply ${candidate.ply}`}>
                  <span>{candidateIndex + 1}</span><strong>{candidate.move_san || candidate.move}</strong><small>{candidate.cp_loss.toFixed(0)} cp</small>
                </button>
              ))}
            </div>
          </div>

          <div className="analysis-note"><Icon name="info" size={15}/><span>{real ? "Evaluations from node-limited Stockfish multi-PV analysis of real Lichess games." : "This synthetic demo uses material-based evaluation. Production runs use Stockfish multi-PV."}</span></div>
          <div className="stepper" aria-label="Navigate evidence positions">
            <button disabled={index === 0} onClick={() => choose(index - 1)}>‹ Previous</button>
            <span>{index + 1} of {moves.length}</span>
            <button className="next" disabled={index === moves.length - 1} onClick={() => choose(index + 1)}>Next ›</button>
          </div>
        </div>
      </div>
    </section>
  );
}

function CaseDetail({ item, real, onDecision }: { item: ReviewCase; real?: boolean; onDecision: (decision: ReviewDecision, reason: string) => Promise<void> }) {
  const [reason, setReason] = useState("Evidence pattern merits a second independent review.");
  const [decision, setDecision] = useState<ReviewDecision>("insufficient");
  const [saving, setSaving] = useState(false);
  const reasons = signalReasons(item);
  useEffect(() => {
    setReason(item.review?.reason ?? "Evidence pattern merits a second independent review.");
    setDecision(item.review?.decision ?? "insufficient");
  }, [item.account_id, item.review?.decision, item.review?.reason]);
  const submit = async () => {
    setSaving(true);
    try { await onDecision(decision, reason); } finally { setSaving(false); }
  };
  return (
    <article className="case-detail">
      <header className="detail-header">
        <div>
          <div className="breadcrumb">Review queue <span>›</span> Case #{item.rank}</div>
          <h1>{item.account_id}</h1>
          <p>{item.rating} rating · {item.games_analyzed} games · {item.moves_analyzed.toLocaleString()} analyzed moves</p>
        </div>
        <div className="risk-summary"><span>Queue score</span><strong>{Math.round(item.risk_score * 100)}</strong><small>{item.confidence_band.replace("_", " ")} confidence</small></div>
      </header>

      <div className="human-banner">
        <div className="banner-icon"><Icon name="shield" size={22}/></div>
        <div><strong>This account was selected for human review—not enforcement</strong><span>The score ranks limited review capacity. Only a reviewer can clear, hold, or escalate the case.</span></div>
        <span className="no-ban-badge">No automatic bans</span>
      </div>

      <section className="why-card">
        <header><div><span className="section-kicker">Why this case is here</span><h2>The model found a repeated pattern across {item.moves_analyzed.toLocaleString()} moves</h2></div><span className="review-priority">Review priority #{item.rank}</span></header>
        <div className="reason-grid">
          {reasons.map((signal, signalIndex) => (
            <div className={signalIndex === 0 ? "primary-signal" : ""} key={signal.label}>
              <span>{signalIndex === 0 ? "Leading signal" : "Supporting signal"}</span>
              <strong>{signal.label}<b>{signal.value}</b></strong>
              <p>{signal.detail}</p>
              <div className="signal-meter"><i style={{ width: `${Math.min(100, signal.strength * 100)}%` }}/></div>
            </div>
          ))}
        </div>
        <p className="risk-explainer"><Icon name="info" size={15}/><span>A queue score of {Math.round(item.risk_score * 100)} means this case ranks highly under the demo model. It does not mean there is a {Math.round(item.risk_score * 100)}% chance the player cheated.</span></p>
      </section>

      <div className="section-heading"><div><span className="section-kicker">Inspect the moves</span><h2>Start with the strongest positions</h2></div><p>Compare the played move, reference move, evaluation, and timing context.</p></div>
      <EvidenceBrowser key={item.account_id} moves={item.evidence.timeline} real={real}/>

      <section className="decision-card">
        <div className="decision-copy"><span className="section-kicker">Record your judgment</span><h2>What should happen next?</h2><p>Choose one outcome, add an internal note, then save. This decision is auditable.</p></div>
        <div className="decision-options" role="radiogroup" aria-label="Review decision">
          <button className={decision === "clear" ? "selected clear" : ""} onClick={() => setDecision("clear")} role="radio" aria-checked={decision === "clear"}><span><Icon name="check"/></span><div><strong>Clear case</strong><small>Evidence does not justify further review</small></div></button>
          <button className={decision === "insufficient" ? "selected hold" : ""} onClick={() => setDecision("insufficient")} role="radio" aria-checked={decision === "insufficient"}><span><Icon name="info"/></span><div><strong>Need more evidence</strong><small>Hold the case for more games or context</small></div></button>
          <button className={decision === "escalate" ? "selected escalate" : ""} onClick={() => setDecision("escalate")} role="radio" aria-checked={decision === "escalate"}><span><Icon name="flag"/></span><div><strong>Escalate</strong><small>Send to a second independent reviewer</small></div></button>
        </div>
        <label htmlFor="review-note">Internal review note</label>
        <textarea id="review-note" value={reason} onChange={(event) => setReason(event.target.value)} rows={3}/>
        <div className="save-row"><span><Icon name="shield" size={15}/> Human decision · logged for audit</span><button disabled={saving || reason.trim().length < 3} onClick={submit}>{saving ? "Saving…" : "Save review decision"}</button></div>
      </section>
    </article>
  );
}

export default function App() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [cases, setCases] = useState<ReviewCase[]>([]);
  const [selectedId, setSelectedId] = useState<string>();
  const [error, setError] = useState<string>();
  const [filter, setFilter] = useState<"all" | "pending" | "reviewed">("all");
  const [query, setQuery] = useState("");

  const refresh = async () => {
    const [nextSummary, nextCases] = await Promise.all([api.summary(), api.cases()]);
    setSummary(nextSummary); setCases(nextCases);
    setSelectedId((current) => current ?? nextCases[0]?.account_id);
  };
  useEffect(() => { refresh().catch((failure: Error) => setError(failure.message)); }, []);
  const visibleCases = useMemo(() => cases.filter((item) => {
    const statusMatch = filter === "all" || (filter === "pending" ? !item.review : !!item.review);
    return statusMatch && item.account_id.toLowerCase().includes(query.toLowerCase());
  }), [cases, filter, query]);
  const selected = cases.find((item) => item.account_id === selectedId) ?? visibleCases[0];
  const decide = async (decision: ReviewDecision, reason: string) => { if (selected) { await api.decide(selected.account_id, decision, reason); await refresh(); } };

  if (error) return <main className="center-state"><BrandMark/><h1>FairPlay couldn’t connect</h1><p>{error}</p></main>;
  if (!summary) return <main className="center-state"><BrandMark/><p>Preparing review workspace…</p></main>;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand"><BrandMark/><div><strong>FairPlay</strong><span>Human Review</span></div></div>
        <div className="workflow" aria-label="Review workflow">
          <div className="done"><span>1</span><div><strong>Scan games</strong><small>Model finds patterns</small></div></div><i>›</i>
          <div className="done"><span>2</span><div><strong>Rank cases</strong><small>Top cases enter queue</small></div></div><i>›</i>
          <div className="active"><span>3</span><div><strong>Review evidence</strong><small>People decide</small></div></div>
        </div>
        <div className="top-actions"><span className="demo-badge"><i/>{summary.manifest.data_mode?.startsWith("real") ? "Real Lichess data" : "Synthetic demo"}</span><button className="avatar" aria-label="Reviewer profile">MP</button></div>
      </header>

      <div className="app-body">
        <aside className="queue-pane">
          <header>
            <div className="queue-title"><div><span className="eyebrow">Top-K selective review</span><h2>Review queue</h2></div><span className="pending-count">{cases.filter((item) => !item.review).length}</span></div>
            <p>Highest-priority accounts appear first. A score ranks review order; it is not a verdict.</p>
          </header>
          <div className="queue-tools">
            <div className="search-field"><Icon name="search" size={16}/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search account ID" aria-label="Search account IDs"/></div>
            <div className="segmented-control" role="group" aria-label="Filter queue">
              {(["all", "pending", "reviewed"] as const).map((value) => <button key={value} className={filter === value ? "active" : ""} onClick={() => setFilter(value)}>{value}</button>)}
            </div>
          </div>
          <div className="queue-heading"><span>{visibleCases.length} cases</span><span>Score</span></div>
          <Queue cases={visibleCases} selected={selected?.account_id} onSelect={(item) => setSelectedId(item.account_id)}/>
          <div className="capacity-card">
            <div><span>Review capacity</span><strong>{summary.reviewed} / {summary.manifest.review_budget ?? 50}</strong></div>
            <div className="capacity-meter"><i style={{ width: `${Math.max(3, summary.reviewed / Math.max(1, summary.manifest.review_budget ?? 50) * 100)}%` }}/></div>
            <p>Only the configured top-K is routed to people.</p>
          </div>
        </aside>

        <main className="content-pane">
          {selected ? <CaseDetail item={selected} real={summary.manifest.data_mode?.startsWith("real")} onDecision={decide}/> : <div className="empty-state">No cases match this filter.</div>}
        </main>
      </div>
    </div>
  );
}
