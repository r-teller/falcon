#!/bin/bash
# Claude Code Status Line - Enhanced with colors
#
# TO REMOVE THIS FEATURE:
# 1. Delete this file: rm ~/.claude/statusline.sh
# 2. Remove "statusLine" block from ~/.claude/settings.json
#

input=$(cat)

# Parse JSON values
MODEL=$(echo "$input" | jq -r '.model.display_name // "Unknown"')
CONTEXT_SIZE=$(echo "$input" | jq -r '.context_window.context_window_size // 0')
USAGE=$(echo "$input" | jq '.context_window.current_usage // null')

# Thinking indicator: thinking.enabled (bool) + effort.level (low/medium/high/xhigh/max)
# Note: keyword-triggered thinking mode (think/think hard/ultrathink) is NOT exposed
# in the statusline JSON — only the on/off boolean and the separate effort level.
THINK_ON=$(echo "$input" | jq -r '.thinking.enabled // empty')
EFFORT=$(echo "$input" | jq -r '.effort.level // empty')
if [ -n "$THINK_ON" ] || [ -n "$EFFORT" ]; then
    THINK_STATE="off"
    [ "$THINK_ON" = "true" ] && THINK_STATE="on"
    if [ -n "$EFFORT" ]; then
        THINK_LABEL="think:${THINK_STATE}/${EFFORT}"
    else
        THINK_LABEL="think:${THINK_STATE}"
    fi
else
    THINK_LABEL=""
fi

# ANSI color codes
RESET="\033[0m"
DIM="\033[2m"
BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
CYAN="\033[36m"
MAGENTA="\033[35m"

# Workspace: folder name + git branch
CWD=$(echo "$input" | jq -r '.cwd // ""')
FOLDER=$(basename "$CWD")
BRANCH=$(git -C "$CWD" rev-parse --abbrev-ref HEAD 2>/dev/null)
if [ -n "$BRANCH" ]; then
    WORKSPACE="${FOLDER}:${BRANCH}"
else
    WORKSPACE="${FOLDER}"
fi

# HARDCODED: Autocompact buffer percentage (not exposed in statusLine JSON)
# Claude Code reserves ~16.5% of context window as autocompact buffer.
# Verify this value periodically by running /context and checking the buffer %.
# Last verified: 2026-03-08 (confirmed via /context screenshot: 33k/200k = 16.5%)
AUTOCOMPACT_BUFFER_PERCENT=16.5

if [ "$USAGE" != "null" ] && [ "$CONTEXT_SIZE" != "0" ]; then
    # Extract token breakdown
    INPUT=$(echo "$USAGE" | jq '.input_tokens // 0')
    CACHE_CREATE=$(echo "$USAGE" | jq '.cache_creation_input_tokens // 0')
    CACHE_READ=$(echo "$USAGE" | jq '.cache_read_input_tokens // 0')
    OUTPUT=$(echo "$USAGE" | jq '.output_tokens // 0')

    # Calculate totals
    CURRENT=$((INPUT + CACHE_CREATE + CACHE_READ))
    TOTAL_K=$((CONTEXT_SIZE / 1000))
    CURRENT_K=$((CURRENT / 1000))

    # Calculate usable capacity (context minus autocompact buffer)
    # Use awk for floating point math
    USABLE_CAPACITY=$(awk "BEGIN {printf \"%.0f\", $CONTEXT_SIZE * (100 - $AUTOCOMPACT_BUFFER_PERCENT) / 100}")
    FREE_UNTIL_COMPACT=$((USABLE_CAPACITY - CURRENT))
    if [ "$FREE_UNTIL_COMPACT" -lt 0 ]; then
        FREE_UNTIL_COMPACT=0
    fi
    FREE_K=$((FREE_UNTIL_COMPACT / 1000))
    PERCENT_UNTIL_COMPACT=$((FREE_UNTIL_COMPACT * 100 / USABLE_CAPACITY))

    # Choose color based on % until autocompact
    if [ "$PERCENT_UNTIL_COMPACT" -lt 20 ]; then
        FREE_COLOR="${RED}${BOLD}"
    elif [ "$PERCENT_UNTIL_COMPACT" -lt 40 ]; then
        FREE_COLOR="${YELLOW}"
    else
        FREE_COLOR="${GREEN}"
    fi

    # Format: Model [· think] | Used/Total | Free % | Breakdown
    printf "${DIM}${CYAN}%s${RESET}" "$MODEL"
    [ -n "$THINK_LABEL" ] && printf " ${DIM}·${RESET} ${YELLOW}%s${RESET}" "$THINK_LABEL"
    printf " ${DIM}|${RESET} "
    printf "${DIM}Used:${RESET} %dk/%dk " "$CURRENT_K" "$TOTAL_K"
    printf "${DIM}|${RESET} ${FREE_COLOR}%d%% until compact${RESET} " "$PERCENT_UNTIL_COMPACT"
    printf "${DIM}| in:%dk cache:%dk out:%dk${RESET} " "$((INPUT/1000))" "$(((CACHE_CREATE+CACHE_READ)/1000))" "$((OUTPUT/1000))"
    printf "${DIM}|${RESET} ${MAGENTA}%s${RESET}" "$WORKSPACE"
else
    printf "${DIM}${CYAN}%s${RESET}" "$MODEL"
    [ -n "$THINK_LABEL" ] && printf " ${DIM}·${RESET} ${YELLOW}%s${RESET}" "$THINK_LABEL"
    printf " ${DIM}| Context: Ready${RESET} ${DIM}|${RESET} ${MAGENTA}%s${RESET}" "$WORKSPACE"
fi
