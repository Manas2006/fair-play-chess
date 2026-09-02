# Model card: FairPlay risk ranker

## Intended use

Prioritize a bounded queue of chess accounts for trained human review. Scores are evidence summaries, not conclusions. The system is not intended for automatic penalties, public accusations, or use outside chess without revalidation.

## Training modes

- **Demo:** synthetic counterfactual move evidence with known assistance rates.
- **Research:** positive–unlabeled learning from public account-level TOS proxies plus matched, unlabeled controls.

The checked-in demo never touches real account labels. Generated artifacts are excluded from Git.

## Inputs

Recent game windows with engine move rank, centipawn loss, position complexity, move time, clock state, rating, time control, and game chronology. Identity fields are excluded from model features.

## Outputs

A calibrated risk estimate plus an evidence bundle. A policy layer selects the top K eligible accounts. Human reviewers may mark a case `clear`, `insufficient`, or `escalate`; escalation is still not an enforcement action.

## Key failure modes

- Strong or titled play can resemble engine play.
- Easy or forced positions inflate raw move-match rates.
- Public TOS status is not a clean engine-cheating label and has unknown marking time.
- Opponent, opening, rating, time-control, and account-age leakage can dominate random splits.
- Calibration changes under prevalence and distribution shift.
- Synthetic assistance may not reproduce adaptive human behavior.
- Correlated games make move-level confidence intervals falsely narrow; bootstrap by account.

## Monitoring

Track input drift by rating and speed, score drift, queue volume, reviewer yield, decision disagreement, calibration on matured labels, per-stratum FPR proxies, and analysis-worker latency. Double-review a blinded sample and report both raw agreement and Cohen's κ.

## Reproducibility

The demo seed, feature list, model family, review budget, and metrics are stored in `artifacts/manifest.json` and the serialized model metadata. Real runs should also record dump month, PGN checksum, Stockfish binary version, node limit, multi-PV, and code commit.
