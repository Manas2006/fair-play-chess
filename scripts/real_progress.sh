#!/bin/bash
# Live progress for the `fairplay real` pipeline. Ctrl+C to exit; it stops on completion.
cd "$(dirname "$0")/.." || exit 1

SLICE="data/raw/lichess_2025-06_150mb.pgn.zst"
TARGET=$((150 * 1024 * 1024))
LOG="${1:-}"  # optional: path to the run log for engine-stage progress

bar() {  # bar <percent> <label>
    local pct=$1 label=$2 width=40
    local filled=$((pct * width / 100))
    printf "\r\033[K[%-${width}s] %3d%%  %s" "$(printf '#%.0s' $(seq 1 $((filled > 0 ? filled : 1))))" "$pct" "$label"
}

while true; do
    if [[ -f artifacts/manifest.json ]] && grep -q real_lichess artifacts/manifest.json 2>/dev/null; then
        bar 100 "done — real artifacts written"
        echo
        break
    fi
    if [[ -n "$LOG" && -f "$LOG" ]]; then
        engine=$(grep -Eo 'engine: [0-9]+/[0-9]+' "$LOG" | tail -1)
        if [[ -n "$engine" ]]; then
            done_n=$(echo "$engine" | grep -Eo '[0-9]+' | head -1)
            total_n=$(echo "$engine" | grep -Eo '[0-9]+' | tail -1)
            bar $((done_n * 100 / total_n)) "stage 4/5 stockfish analysis ($done_n/$total_n accounts)"
            sleep 2; continue
        fi
        if [[ -f data/processed/real/cohort_games.json ]]; then
            bar 55 "stage 4/5 stockfish analysis warming up ($(pgrep stockfish 2>/dev/null | wc -l | tr -d ' ') engines running)"
            sleep 2; continue
        fi
        if grep -q '^cohort:' "$LOG" 2>/dev/null; then
            bar 50 "stage 4/5 extracting cohort games from slice"
            sleep 2; continue
        fi
        labels=$(grep -c '^labels:' "$LOG" 2>/dev/null)
        if [[ "$labels" -gt 0 ]]; then
            positives=$(grep '^labels:' "$LOG" | tail -1 | grep -Eo '[0-9]+ proxy' | grep -Eo '[0-9]+')
            bar $((positives > 40 ? 99 : positives * 100 / 40)) "stage 3/5 fetching labels (${positives:-0}/40 proxy positives)"
            sleep 2; continue
        fi
    fi
    if [[ -f "$SLICE" ]]; then
        size=$(stat -f%z "$SLICE")
        if [[ "$size" -lt "$TARGET" ]]; then
            bar $((size * 100 / TARGET)) "stage 1/5 downloading slice ($((size / 1048576))/150 MB)"
        elif [[ -f data/processed/real/cohort_games.json ]]; then
            bar 50 "stage 4/5 stockfish analysis starting"
        elif [[ -f data/processed/real/labels.json ]]; then
            bar 40 "stage 3/5 fetching labels"
        elif [[ -f data/processed/real/players.json ]]; then
            bar 30 "stage 3/5 fetching labels"
        else
            bar 25 "stage 2/5 scanning players"
        fi
    else
        bar 0 "waiting for download to start"
    fi
    sleep 2
done
