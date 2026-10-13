#!/usr/bin/env bash
# Claude Statusline Plus — enhanced fork of Astro-Han/claude-pace
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Astro-Han; enhancements Copyright (c) 2026 VallierDev
# Line1: model (ctx) effort | project (branch) Nf +A -D
# Line2: bar PCT% CL | quota countdowns | cache TTL | last model activity

# Disable glob expansion so unquoted vars with wildcards (e.g. DIR paths)
# are never accidentally expanded into filename lists.
set -f
input=$(cat)
[ -z "$input" ] && {
  echo "Claude"
  exit 0
}
command -v jq >/dev/null || {
  echo "Claude [needs jq]"
  exit 0
}

# Fail gently when the host sends malformed/non-object session data.
if ! jq -e 'type == "object"' >/dev/null 2>&1 <<<"$input"; then
  printf 'Claude [invalid session data]\n'
  exit 0
fi

# ── Colors & Utilities ──
# C=Cyan G=Green Y=Yellow R=Red D=Dim N=Normal (reset)
# Store real escape bytes so final output does not need echo -e interpretation.
C=$'\033[36m' G=$'\033[32m' Y=$'\033[33m' R=$'\033[31m' D=$'\033[2m' N=$'\033[0m'
# Cache records use ASCII Unit Separator so legal Git ref names cannot split
# serialized fields and empty values survive round-trips through read.
SEP=$'\037'
NOW=$(date +%s)
# Returns true when the candidate cache dir is a real directory owned by the
# current user, writable, and not a symlink into a foreign-controlled path.
_cache_dir_ok() { [ -d "$1" ] && [ ! -L "$1" ] && [ -O "$1" ] && [ -w "$1" ]; }
# Reads one cache record into CACHE_FIELDS, supporting the current separator
# and the legacy pipe format used by older cache files.
_read_cache_record() {
  local line="$1" delim rest field
  CACHE_FIELDS=()
  if [[ "$line" == *"$SEP"* ]]; then
    delim="$SEP"
  else
    delim='|'
  fi
  rest="$line"
  while [[ "$rest" == *"$delim"* ]]; do
    field=${rest%%"$delim"*}
    CACHE_FIELDS+=("$field")
    rest=${rest#*"$delim"}
  done
  CACHE_FIELDS+=("$rest")
}
# Loads and parses one cache file into CACHE_FIELDS.
_load_cache_record_file() {
  local path="$1" line=""
  [ -f "$path" ] || return 1
  IFS= read -r line <"$path" || line=""
  _read_cache_record "$line"
}
# Writes one cache record straight to its final path. This used to go through a
# mktemp file and an mv for atomicity, but Claude Code cancels the status line
# script whenever a refresh arrives mid-run, so every cancellation between the
# write and the mv stranded a uniquely named temp file forever — one reporter had
# 3008 of them. Atomicity was never needed here: the record is one short line of
# git data with a 5s TTL, so a torn write is just a cache miss that the reader
# already sanitizes and the next run recomputes. Dropping the temp file also drops
# two subprocess spawns per refresh and shrinks the cancellable window to a single
# builtin. Symlinks must be refused explicitly: mv used to replace the link
# itself, while > follows it.
_write_cache_record() {
  local path="$1" IFS="$SEP"
  shift
  [ ! -L "$path" ] || return 1
  printf '%s\n' "$*" >"$path" 2>/dev/null
}
# Computes remaining whole minutes until a future epoch. Missing or expired
# timestamps return an empty string so callers can skip countdown formatting.
_minutes_until() {
  local epoch="$1" mins
  [[ "$epoch" =~ ^[0-9]+$ ]] && ((epoch > 0)) || return
  mins=$(((epoch - NOW) / 60))
  ((mins < 0)) && mins=0
  printf '%s\n' "$mins"
}
# Collects live Git metadata for DIR. On non-repos, leaves defaults in place
# and returns non-zero so callers can decide whether to cache the empty result.
_collect_git_info() {
  BR="" FC=0 AD=0 DL=0
  git -C "$DIR" rev-parse --git-dir >/dev/null 2>&1 || return 1
  BR=$(git -C "$DIR" --no-optional-locks branch --show-current 2>/dev/null)
  while IFS=$'\t' read -r a d _; do
    # Skip binary files (reported as "-" instead of a number).
    [[ "$a" =~ ^[0-9]+$ ]] || continue
    FC=$((FC + 1))
    AD=$((AD + a))
    DL=$((DL + d))
  done < <(git -C "$DIR" --no-optional-locks diff HEAD --numstat 2>/dev/null)
}
# Cache only inside a user-owned, non-symlinked directory. If no safe root is
# available, disable caching for this run instead of falling back to shared /tmp.
_CD="" CACHE_OK=0
for _BASE in "${XDG_RUNTIME_DIR:-}" "${HOME}/.cache"; do
  [ -n "$_BASE" ] || continue
  _CAND="${_BASE%/}/claude-pace"
  # shellcheck disable=SC2174  # -p only creates leaf here; parent already exists
  [ -e "$_CAND" ] || mkdir -p -m 700 "$_CAND" 2>/dev/null || continue
  _cache_dir_ok "$_CAND" || continue
  _CD="$_CAND"
  CACHE_OK=1
  break
done
# Returns true (exit 0) when file is missing or older than $2 seconds.
_stale() { [ ! -f "$1" ] || [ $((NOW - $(stat -f%m "$1" 2>/dev/null || stat -c%Y "$1" 2>/dev/null || echo 0))) -gt "$2" ]; }

# ── Parse stdin + settings in one jq call ──
# Fields: MODEL DIR PCT CTX COST EFF HAS_RL U5 U7 R5 R7 TIN SID
#         CACHE_WARM CACHE_SEEN CACHE_EXP CACHE_TTL
# Read settings into a shell var rather than process substitution so the jq
# --argjson path works on Windows Git Bash (where /proc/<pid>/fd/N used by
# <(...) is unavailable and --slurpfile silently fails, yielding empty fields).
HAS_RL=0
_SETTINGS=$(cat "$HOME/.claude/settings.json" 2>/dev/null)
echo "$_SETTINGS" | jq -e 'type == "object"' >/dev/null 2>&1 || _SETTINGS='{}'
IFS=$'\t' read -r MODEL DIR PCT CTX COST EFF HAS_RL U5 U7 R5 R7 TIN SID CACHE_WARM CACHE_SEEN CACHE_EXP CACHE_TTL < <(
  jq -r --argjson cfg "$_SETTINGS" \
    '[(.model.display_name//"?"),(.workspace.project_dir//.workspace.current_dir//"."|gsub("\\\\";"/")),
    (.context_window.used_percentage//0|floor),(.context_window.context_window_size//0),
    (.cost.total_cost_usd//0),
    (.effort.level//$cfg.effortLevel//"default"),
    (if .rate_limits then 1 else 0 end),
    (.rate_limits.five_hour.used_percentage//null|if type=="number" then floor else "--" end),
    (.rate_limits.seven_day.used_percentage//null|if type=="number" then floor else "--" end),
    (.rate_limits.five_hour.resets_at//0),
    (.rate_limits.seven_day.resets_at//0),
    (if (.context_window.total_input_tokens|type)=="number" then (.context_window.total_input_tokens|floor) else -1 end),
    # Bash read collapses empty TSV fields; keep this optional slot nonempty.
    (.session_id//.sessionId//":"|if .=="" then ":" else . end),
    (.prompt_cache.warm//false|tostring),
    (.prompt_cache.caching_observed//false|tostring),
    (.prompt_cache.expires_at//0),
    (.prompt_cache.ttl//"--")]|@tsv' <<<"$input"
)
case "${EFF:-default}" in low) EF='low' ;; high) EF='high' ;; xhigh) EF='xhigh' ;; max) EF='max' ;; *) EF='medium' ;; esac

# The last model activity is the latest assistant response carrying API usage.
# Tool results and background queue events are not model requests and must not
# reset this timer. The cache TTL is read separately from prompt_cache below.
_session_idle_label() {
  local sid="$1" dir="$2" key path last_ts last_epoch age_s mins
  [[ "$sid" =~ ^[A-Za-z0-9._-]+$ ]] || return
  [[ "$dir" == /* ]] || return
  key="-${dir#/}"
  key="${key//\//-}"
  path="$HOME/.claude/projects/${key}/${sid}.jsonl"
  [ -f "$path" ] || return
  last_ts=$(tail -n 400 "$path" 2>/dev/null | jq -r 'select(.type=="assistant" and (.message.usage|type)=="object" and (.isSidechain != true) and (.timestamp|type)=="string") | .timestamp' 2>/dev/null | sort | tail -1)
  [[ -n "$last_ts" ]] || return
  last_ts=$(printf '%s' "$last_ts" | sed -E 's/\.[0-9]+Z$/Z/')
  last_epoch=$(/bin/date -j -u -f '%Y-%m-%dT%H:%M:%SZ' "$last_ts" '+%s' 2>/dev/null || /bin/date -d "$last_ts" '+%s' 2>/dev/null)
  [[ "$last_epoch" =~ ^[0-9]+$ ]] || return
  age_s=$((NOW - last_epoch))
  ((age_s < 0)) && age_s=0
  mins=$((age_s / 60))
  if ((mins >= 60)); then
    printf "${R}last %dh %dm${N}" $((mins / 60)) $((mins % 60))
  else
    printf "${D}last %dm${N}" "$mins"
  fi
}
IDLE_LABEL=$(_session_idle_label "$SID" "$DIR")

# Claude Code's prompt_cache.expires_at is the real cache TTL boundary. Its
# epoch keeps counting down on refreshInterval even when the session is idle.
CACHE_LABEL=""
if [[ "$CACHE_EXP" =~ ^[0-9]+$ ]] && ((CACHE_EXP > 0)); then
  remain_s=$((CACHE_EXP - NOW))
  if ((remain_s > 0)); then
    remain_m=$(((remain_s + 59) / 60))
    if ((remain_m <= 5)); then CC=$R; elif ((remain_m <= 15)); then CC=$Y; else CC=$G; fi
    CACHE_LABEL="${CC}cache ${remain_m}m${N}"
  else
    CACHE_LABEL="${R}cache cold${N}"
  fi
elif [[ "$CACHE_WARM" == "true" ]]; then
  CACHE_LABEL="${G}cache warm${N}"
elif [[ "$CACHE_SEEN" == "true" ]]; then
  CACHE_LABEL="${R}cache cold${N}"
else
  CACHE_LABEL="${D}cache --${N}"
fi

# ── Auto-compact window: track usage against the compaction threshold ──
# When CLAUDE_CODE_AUTO_COMPACT_WINDOW is set, compaction fires at that token
# count, not the model's full window. Recompute PCT against it and relabel CTX
# so the bar measures "distance to compaction", matching the desktop app's bar
# (e.g. 49.8k / 400.0k). The jq above emits TIN=-1 only when CC omits
# total_input_tokens entirely (old CC); the ^[0-9]+$ test rejects that and falls
# back to the full window. A present zero (fresh-session first frame, before the
# first API response) passes, so the bar measures against the cap from the start
# instead of flashing the full window while the env var is set.
ACW="${CLAUDE_CODE_AUTO_COMPACT_WINDOW:-0}"
if [[ "$ACW" =~ ^[0-9]+$ ]] && ((ACW > 0)) && [[ "$TIN" =~ ^[0-9]+$ ]]; then
  # Compaction can't exceed the real window; clamp so the label stays honest.
  ((CTX > 0 && ACW > CTX)) && ACW=$CTX
  PCT=$((TIN * 100 / ACW))
  ((PCT > 100)) && PCT=100
  CTX=$ACW
fi

# ── Context label (needed by MODEL_SHORT and line 2) ──
if ((CTX >= 1000000)); then
  CL="$((CTX / 1000000))M"
elif ((CTX > 0)); then
  CL="$((CTX / 1000))K"
else CL=""; fi

# ── MODEL_SHORT: strip redundant context label ──
MODEL=${MODEL/ context)/)}
[[ "$CTX" -gt 0 && "$MODEL" != *"("* ]] && MODEL="${MODEL} (${CL})"
# Cap "MODEL EF" at 28 chars; 28 fits the longest effort word ('medium', 6 chars)
# plus a typical "Sonnet 4.6 (200K)" without ellipsis.
_ML="${MODEL} ${EF}"
((${#_ML} > 28)) && MODEL="${MODEL:0:$((28 - 2 - ${#EF}))}…"

# ── Progress Bar ──
F=$((PCT / 10))
((F < 0)) && F=0
((F > 10)) && F=10
if ((PCT >= 90)); then BC=$R; elif ((PCT >= 70)); then BC=$Y; else BC=$G; fi
BAR=""
for ((i = 0; i < F; i++)); do BAR+='█'; done
for ((i = F; i < 10; i++)); do BAR+='░'; done

# ── Git Info (5s disposable cache) ──
# Cache key encodes DIR so concurrent sessions in different repos don't clash.
# Records are disposable: anything unreadable or torn falls through to the
# sanitizing guards below and is recomputed on the next run.
BR="" FC=0 AD=0 DL=0
if [[ "$CACHE_OK" == "1" ]]; then
  GC="${_CD}/claude-sl-git-$(printf '%s' "$DIR" | { shasum 2>/dev/null || sha1sum; } | cut -c1-16)"
  if _stale "$GC" 5; then
    if _collect_git_info; then
      _write_cache_record "$GC" "$BR" "$FC" "$AD" "$DL"
    else
      _write_cache_record "$GC" "" "" "" ""
    fi
  elif _load_cache_record_file "$GC"; then
    BR=${CACHE_FIELDS[0]:-}
    FC=${CACHE_FIELDS[1]:-}
    AD=${CACHE_FIELDS[2]:-}
    DL=${CACHE_FIELDS[3]:-}
  fi
  # Reject cache corruption before arithmetic or terminal output formatting.
  [[ "$FC" =~ ^[0-9]+$ ]] || FC=0
  [[ "$AD" =~ ^[0-9]+$ ]] || AD=0
  [[ "$DL" =~ ^[0-9]+$ ]] || DL=0
else
  _collect_git_info || true
fi

# ── Project Name + Line 1 Right Section ──
# Extract project name. Worktree: save repo name explicitly.
PN="${DIR##*/}"
IS_WT=0 _REPO=""
if [[ "${DIR/#$HOME/\~}" =~ /([^/]+)/\.claude/worktrees/([^/]+) ]]; then
  IS_WT=1
  _REPO="${BASH_REMATCH[1]}"
  _WT_NAME="${BASH_REMATCH[2]}"
  PN="$_REPO"
fi
((${#PN} > 25)) && PN="${PN:0:25}…"

# Format: project (branch) [git stats]
L1R="$PN"
if [ -n "$BR" ]; then
  ((${#BR} > 35)) && BR="${BR:0:35}…"
  L1R+=" (${BR})"
  ((FC > 0)) 2>/dev/null && L1R+=" ${FC}f ${G}+${AD}${N} ${R}-${DL}${N}"
elif [[ "$IS_WT" == "1" ]]; then
  # Detached HEAD in worktree: show repo/worktree to preserve identity
  L1R="${_REPO}/${_WT_NAME}"
  ((${#L1R} > 25)) && L1R="${L1R:0:25}…"
fi

# Usage data: read stdin rate_limits when available. When absent we show
# placeholders and the session cost instead of falling back to a possibly stale
# (or wrong-account) cached snapshot. See docs/decisions/2026-05-20-quota-cache-removal.md.
SHOW_COST=0
if [[ "$HAS_RL" == "1" ]]; then
  # Stdin path: real-time, no network. U5/U7 already set by jq read above.
  # Guard: resets_at=0 means field missing, leave RM empty so _usage skips it.
  RM5=$(_minutes_until "$R5")
  RM7=$(_minutes_until "$R7")
else
  U5="--" U7="--" RM5="" RM7=""
  SHOW_COST=1
fi

# Format the absolute reset time in the local timezone.
_reset_label() {
  local epoch="$1" reset_date today clock
  [[ "$epoch" =~ ^[0-9]+$ ]] && ((epoch > 0)) || return
  reset_date=$(date -r "$epoch" '+%Y-%m-%d' 2>/dev/null || date -d "@$epoch" '+%Y-%m-%d' 2>/dev/null) || return
  today=$(date '+%Y-%m-%d') || return
  if [[ "$reset_date" == "$today" ]]; then
    clock=$(date -r "$epoch" '+%H:%M' 2>/dev/null || date -d "@$epoch" '+%H:%M' 2>/dev/null) || return
    printf '↻%s' "$clock"
  else
    clock=$(date -r "$epoch" '+%m-%d %H:%M' 2>/dev/null || date -d "@$epoch" '+%m-%d %H:%M' 2>/dev/null) || return
    printf '↻%s' "$clock"
  fi
}

# Combined usage formatter: used% [pace delta] (countdown + reset time)
_usage() {
  local u="${1:---}" rm="$2" w="$3" reset_epoch="${4:-}" reset_label
  if [[ ! "$u" =~ ^[0-9]+$ ]]; then
    printf "%s" "$u"
  else
    if ((u >= 90)); then printf "${R}%d%%${N}" "$u"; elif ((u >= 70)); then printf "${Y}%d%%${N}" "$u"; else printf "${G}%d%%${N}" "$u"; fi
    if [[ "$rm" =~ ^[0-9]+$ ]] && ((rm <= w)); then
      # Pace delta: positive = over pace (overspend), negative = under pace (surplus).
      local d=$((u - (w - rm) * 100 / w))
      ((d > 0)) && printf " ${R}⇡%d%%${N}" "$d"
      ((d < 0)) && printf " ${G}⇣%d%%${N}" "${d#-}"
    fi
  fi
  [[ "$rm" =~ ^[0-9]+$ ]] || return
  if ((rm >= 1440)); then
    local days=$((rm / 1440)) hours=$(((rm % 1440) / 60)) minutes=$((rm % 60))
    if ((hours > 0)); then
      printf " ${D}%dd %dh %dm${N}" "$days" "$hours" "$minutes"
    elif ((minutes > 0)); then
      printf " ${D}%dd %dm${N}" "$days" "$minutes"
    else
      printf " ${D}%dd${N}" "$days"
    fi
  elif ((rm >= 60)); then
    printf " ${D}%dh %dm${N}" $((rm / 60)) $((rm % 60))
  else
    printf " ${D}%dm${N}" "$rm"
  fi
  reset_label=$(_reset_label "$reset_epoch")
  [[ -n "$reset_label" ]] && printf " ${D}%s${N}" "$reset_label"
}

# ── Output Assembly (symmetric single-pipe alignment) ──

# Build plain-text left sections for width measurement (no ANSI codes).
L1_PLAIN="${MODEL} ${EF}"
L2_PLAIN="${BAR} ${PCT}% ${CL}"
# Pad shorter side so | aligns on both lines.
W1=${#L1_PLAIN} W2=${#L2_PLAIN}
PAD1="" PAD2=""
if ((W1 > W2)); then
  printf -v PAD2 "%*s" $((W1 - W2)) ""
elif ((W2 > W1)); then
  printf -v PAD1 "%*s" $((W2 - W1)) ""
fi

# Line 1: model (context) effort | project (branch) git-stats
L1="${C}${MODEL} ${EF}${N}${PAD1} ${D}|${N}  ${L1R}"

# Line 2: bar pct% CL | 5h used% ...  7d used% ...
L2="${BC}${BAR}${N} ${PCT}% ${CL}${PAD2} ${D}|${N}  5h $(_usage "$U5" "$RM5" 300 "$R5")  7d $(_usage "$U7" "$RM7" 10080 "$R7")"
L2+="  $CACHE_LABEL"
[[ -n "$IDLE_LABEL" ]] && L2+="  $IDLE_LABEL"
# Session cost: only when usage data is unavailable in stdin.
if [[ "$SHOW_COST" == "1" ]]; then
  printf -v _CS "\$%.2f" "$COST" 2>/dev/null
  [[ "$_CS" != "\$0.00" ]] && L2+="  $_CS"
fi

printf '%s\n' "$L1"
printf '%s\n' "$L2"
