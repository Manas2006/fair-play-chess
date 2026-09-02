import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import type { ReviewCase, ReviewDecision, Summary, TimelineMove } from "./types";

const percent = (value = 0, digits = 1) => `${(value * 100).toFixed(digits)}%`;
const PIECES: Record<string, string> = {
  K: "♔", Q: "♕", R: "♖", B: "♗", N: "♘", P: "♙",
  k: "♚", q: "♛", r: "♜", b: "♝", n: "♞", p: "♟"
};

function Icon({ name, size = 18 }: { name: "queue" | "chart" | "settings" | "search" | "chevron" | "shield"; size?: number }) {
  const paths = {
    queue: <><path d="M4 5.5h16M4 12h16M4 18.5h16"/><circle cx="2" cy="5.5" r=".5"/><circle cx="2" cy="12" r=".5"/><circle cx="2" cy="18.5" r=".5"/></>,
    chart: <><path d="M4 19V9m6 10V5m6 14v-7m4 7V3"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.6v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/></>,
    search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 4 4"/></>,
    chevron: <path d="m9 18 6-6-6-6"/>,
    shield: <path d="M12 2.5 20 6v5.5c0 5-3.4 8.6-8 10-4.6-1.4-8-5-8-10V6l8-3.5Z"/>
  };
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

function BrandMark() {
  return <div className="brand-mark" aria-hidden="true"><Icon name="shield" size={22}/><span>♞</span></div>;
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
      <small>Demo eval</small>
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

function Queue({ cases, selected, onSelect }: { cases: ReviewCase[]; selected?: string; onSelect: (item: ReviewCase) => void }) {
  return (
    <div className="case-list" aria-label="Review cases">
      {cases.map((item) => (
        <button type="button" className={`case-row ${selected === item.account_id ? "selected" : ""}`} key={item.account_id} onClick={() => onSelect(item)}>
          <span className={`status-orb ${item.review?.decision ?? "pending"}`} />
          <span className="case-copy">
            <span><strong>Case {String(item.rank).padStart(2, "0")}</strong><time>{item.dominant_speed}</time></span>
            <small>{item.account_id}</small>
            <span className="case-meta">{item.rating} rating · {item.games_analyzed} games</span>
          </span>
          <span className={`risk-score ${item.confidence_band}`}>{Math.round(item.risk_score * 100)}</span>
          <Icon name="chevron" size={15}/>
        </button>
      ))}
    </div>
  );
}

function EvidenceBrowser({ moves }: { moves: TimelineMove[] }) {
  const [index, setIndex] = useState(0);
  useEffect(() => setIndex(0), [moves]);
  const move = moves[Math.min(index, Math.max(0, moves.length - 1))];
  if (!move) return <div className="empty-state">No position evidence is available.</div>;
  const choose = (next: number) => setIndex(Math.max(0, Math.min(moves.length - 1, next)));
  return (
    <section className="evidence-browser">
      <div className="evidence-toolbar">
        <div>
          <span className="section-kicker">Position evidence</span>
          <h3>{move.game_id} <span>· Ply {move.ply}</span></h3>
        </div>
        <div className="stepper" aria-label="Navigate evidence positions">
          <button aria-label="Previous position" disabled={index === 0} onClick={() => choose(index - 1)}>‹</button>
          <span>{index + 1} of {moves.length}</span>
          <button aria-label="Next position" disabled={index === moves.length - 1} onClick={() => choose(index + 1)}>›</button>
        </div>
      </div>
      <div className="analysis-layout">
        <Chessboard move={move} />
        <div className="move-inspector">
          <div className="move-summary">
            <div><span>Played</span><strong>{move.move_san || move.move}</strong><code>{move.move}</code></div>
            <div><span>Reference move</span><strong>{move.best_move_san || move.best_move}</strong><code>{move.best_move}</code></div>
          </div>
          <div className="signal-details">
            <div><span>Centipawn loss</span><strong>{move.cp_loss.toFixed(1)}</strong></div>
            <div><span>Think time</span><strong>{move.move_time_s.toFixed(1)}s</strong></div>
            <div><span>Complexity</span><strong>{percent(move.complexity, 0)}</strong></div>
            <div><span>Reference match</span><strong>{move.engine_match ? "Matched" : "No"}</strong></div>
          </div>
          <p className="analysis-note">The board shows the legal position after the played move. Positive values favor White. This demo uses a material-based evaluation; real runs use Stockfish.</p>
          <div className="position-strip">
            {moves.slice(0, 12).map((candidate, candidateIndex) => (
              <button key={`${candidate.game_id}-${candidate.ply}`} className={candidateIndex === index ? "active" : ""} onClick={() => choose(candidateIndex)} aria-label={`Open ${candidate.game_id} ply ${candidate.ply}`}>
                <span>{candidate.move_san || candidate.move}</span><small>{candidate.cp_loss.toFixed(0)} cp</small>
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function CaseDetail({ item, onDecision }: { item: ReviewCase; onDecision: (decision: ReviewDecision, reason: string) => Promise<void> }) {
  const [reason, setReason] = useState("Evidence pattern merits a second independent review.");
  const [saving, setSaving] = useState(false);
  useEffect(() => setReason(item.review?.reason ?? "Evidence pattern merits a second independent review."), [item.account_id, item.review?.reason]);
  const submit = async (decision: ReviewDecision) => {
    setSaving(true);
    try { await onDecision(decision, reason); } finally { setSaving(false); }
  };
  return (
    <article className="case-detail">
      <header className="detail-header">
        <div>
          <div className="breadcrumb">Review Queue <span>›</span> Case {String(item.rank).padStart(2, "0")}</div>
          <h1>{item.account_id}</h1>
          <p>Anonymized account snapshot · {item.moves_analyzed.toLocaleString()} analyzed decisions</p>
        </div>
        <div className="risk-summary"><span>Calibrated risk</span><strong>{Math.round(item.risk_score * 100)}%</strong><small>{item.confidence_band.replace("_", " ")} confidence</small></div>
      </header>

      <div className="human-banner"><Icon name="shield" size={20}/><div><strong>Human judgment required</strong><span>This score prioritizes review. It is not a finding of misconduct.</span></div></div>

      <section className="evidence-overview">
        <div><span>Engine match</span><strong>{percent(item.evidence.engine_match_rate)}</strong><small>all analyzed moves</small></div>
        <div><span>Median CP loss</span><strong>{item.evidence.median_cp_loss.toFixed(1)}</strong><small>lower is stronger</small></div>
        <div><span>Hard-position match</span><strong>{percent(item.evidence.hard_position_match_rate)}</strong><small>complex decisions</small></div>
        <div><span>Review state</span><strong className="capitalize">{item.review?.decision ?? "Pending"}</strong><small>{item.review ? "decision recorded" : "awaiting reviewer"}</small></div>
      </section>

      <EvidenceBrowser key={item.account_id} moves={item.evidence.timeline}/>

      <section className="decision-card">
        <div className="decision-copy"><span className="section-kicker">Reviewer decision</span><h3>What does the evidence support?</h3></div>
        <label htmlFor="review-note">Internal note</label>
        <textarea id="review-note" value={reason} onChange={(event) => setReason(event.target.value)} rows={2}/>
        <div className="review-actions">
          <button disabled={saving || reason.length < 3} className="secondary-action clear" onClick={() => submit("clear")}>Clear case</button>
          <button disabled={saving || reason.length < 3} className="secondary-action" onClick={() => submit("insufficient")}>Need more evidence</button>
          <button disabled={saving || reason.length < 3} className="primary-action" onClick={() => submit("escalate")}>Escalate for review</button>
        </div>
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
  useEffect(() => { refresh().catch((reason: Error) => setError(reason.message)); }, []);
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
      <header className="window-bar">
        <div className="traffic-lights" aria-hidden="true"><i/><i/><i/></div>
        <div className="window-title"><BrandMark/><strong>FairPlay Review</strong><span>Research workspace</span></div>
        <div className="window-actions"><span className="model-status"><i/> Demo model online</span><button className="avatar" aria-label="Reviewer profile">MP</button></div>
      </header>

      <div className="app-body">
        <aside className="sidebar">
          <nav aria-label="Primary navigation">
            <span className="nav-label">Workspace</span>
            <button className="nav-item active"><Icon name="queue"/>Review queue<span>{cases.filter((item) => !item.review).length}</span></button>
            <button className="nav-item"><Icon name="chart"/>Model health</button>
            <span className="nav-label secondary">System</span>
            <button className="nav-item"><Icon name="settings"/>Settings</button>
          </nav>
          <div className="sidebar-card">
            <span>Today’s capacity</span><strong>{summary.reviewed} <small>of {summary.manifest.review_budget ?? 50}</small></strong>
            <div><i style={{ width: `${Math.max(3, summary.reviewed / Math.max(1, summary.manifest.review_budget ?? 50) * 100)}%` }}/></div>
            <p>The model routes cases.<br/>People make decisions.</p>
          </div>
          <div className="data-label"><i/>Synthetic demonstration data</div>
        </aside>

        <section className="queue-pane">
          <header><div><h2>Review Queue</h2><p>Highest-confidence cases first</p></div></header>
          <div className="search-field"><Icon name="search" size={16}/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search cases" aria-label="Search cases"/></div>
          <div className="segmented-control" role="group" aria-label="Filter queue">
            {(["all", "pending", "reviewed"] as const).map((value) => <button key={value} className={filter === value ? "active" : ""} onClick={() => setFilter(value)}>{value}</button>)}
          </div>
          <div className="queue-heading"><span>{visibleCases.length} cases</span><span>Risk</span></div>
          <Queue cases={visibleCases} selected={selected?.account_id} onSelect={(item) => setSelectedId(item.account_id)}/>
        </section>

        <main className="content-pane">
          {selected ? <CaseDetail item={selected} onDecision={decide}/> : <div className="empty-state">No cases match this filter.</div>}
        </main>
      </div>
    </div>
  );
}
