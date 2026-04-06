#!/bin/bash

input=$(cat)
cur=$(echo "$input" | jq -r '.context_window.used_percentage // 0 | floor')
model=$(echo "$input" | jq -r '.model.display_name // .model.id // "?"')
effort=$(echo "$input" | jq -r '.effort // .effort_level // .effortLevel // .model.effort // .model.reasoningEffort // empty')
if [ -z "$effort" ]; then
  effort=$(jq -r '.effortLevel // .effort // .reasoningEffort // "auto"' ~/.claude/settings.json 2>/dev/null)
fi
[ -z "$effort" ] && effort="auto"
branch=$(git -C "$PWD" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '-')
added=$(echo "$input" | jq -r '.cost.total_lines_added // 0')
removed=$(echo "$input" | jq -r '.cost.total_lines_removed // 0')
in_tok=$(echo "$input" | jq -r '.context_window.total_input_tokens // 0')
out_tok=$(echo "$input" | jq -r '.context_window.total_output_tokens // 0')
dirty=$(git -C "$PWD" status --porcelain 2>/dev/null | head -1)
rate_5h=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty | floor')
rate_7d=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty | floor')
rate_5h_reset=$(echo "$input" | jq -r '.rate_limits.five_hour.resets_at // empty')
[ -n "$rate_5h_reset" ] && rate_5h_time=$(date -r "$rate_5h_reset" '+%H:%M' 2>/dev/null || date -d "@$rate_5h_reset" '+%H:%M' 2>/dev/null)
rate_7d_reset=$(echo "$input" | jq -r '.rate_limits.seven_day.resets_at // empty')
[ -n "$rate_7d_reset" ] && rate_7d_time=$(date -r "$rate_7d_reset" '+%a %H:%M' 2>/dev/null || date -d "@$rate_7d_reset" '+%a %H:%M' 2>/dev/null)

GREEN=$'\033[32m'
YELLOW=$'\033[33m'
RED=$'\033[31m'
ORANGE=$'\033[38;2;255;140;0m'
CYAN=$'\033[36m'
BOLD_CYAN=$'\033[1;36m'
BRIGHT_WHITE=$'\033[97m'
DIM=$'\033[2m'
RESET=$'\033[0m'

if [ "$cur" -lt 40 ]; then
  ctx_color=$GREEN
elif [ "$cur" -lt 60 ]; then
  ctx_color=$YELLOW
else
  ctx_color=$RED
fi

if [ "$branch" = "main" ] || [ "$branch" = "master" ]; then
  branch_color=$ORANGE
else
  branch_color=$CYAN
fi

fmt_tok() { awk "BEGIN{v=$1; if(v>=1000000) printf \"%.1fM\",v/1000000; else if(v>=1000) printf \"%.1fk\",v/1000; else printf \"%d\",v}"; }
in_fmt=$(fmt_tok "$in_tok")
out_fmt=$(fmt_tok "$out_tok")

rate_color() { if [ "$1" -lt 50 ]; then echo "$GREEN"; elif [ "$1" -lt 80 ]; then echo "$YELLOW"; else echo "$RED"; fi; }
section_rate=""
if [ -n "$rate_5h" ]; then
  r5_color=$(rate_color "$rate_5h")
  r7_color=$(rate_color "$rate_7d")
  reset_str=""
  [ -n "$rate_5h_time" ] && reset_str=" ${RESET}${DIM}(reset at ${YELLOW}${rate_5h_time}${RESET}${DIM})${RESET}"
  reset_7d_str=""
  [ -n "$rate_7d_time" ] && reset_7d_str=" ${RESET}${DIM}(reset at ${YELLOW}${rate_7d_time}${RESET}${DIM})${RESET}"
  section_rate=" │ ${BRIGHT_WHITE}usage 5h window: ${RESET}${r5_color}${rate_5h}%%${reset_str} ${BRIGHT_WHITE}7d: ${RESET}${r7_color}${rate_7d}%%${reset_7d_str}"
fi

if [ -n "$dirty" ]; then
  dirty_files=$(git -C "$PWD" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  git_dirty=" ${YELLOW}● ${dirty_files}f${RESET}"
else
  git_dirty=" ${GREEN}✔${RESET}"
fi

# Peak detection: weekdays 5am-11am PT limits burn faster
# Convert PT boundaries to IL dynamically (handles DST differences)
peak_start_il=$(TZ='Asia/Jerusalem' date -jf '%H %Z' '05 PDT' '+%-H' 2>/dev/null || TZ='Asia/Jerusalem' date -d '05:00 America/Los_Angeles' '+%-H' 2>/dev/null)
peak_end_il=$(TZ='Asia/Jerusalem' date -jf '%H %Z' '11 PDT' '+%-H' 2>/dev/null || TZ='Asia/Jerusalem' date -d '11:00 America/Los_Angeles' '+%-H' 2>/dev/null)
# Fallback if conversion fails
[ -z "$peak_start_il" ] && peak_start_il=15
[ -z "$peak_end_il" ] && peak_end_il=21
day_of_week=$(TZ='Asia/Jerusalem' date +%u)  # 1=Mon, 7=Sun
hour_il=$(TZ='Asia/Jerusalem' date +%-H)
if [ "$day_of_week" -ge 6 ] || [ "$hour_il" -lt "$peak_start_il" ] || [ "$hour_il" -ge "$peak_end_il" ]; then
  offpeak_now="${GREEN}✔ off-peak now (limits burn slower)${RESET}"
else
  offpeak_now="${RED}✘ peak now (limits burn faster)${RESET}"
fi

printf "${ctx_color}ctx: ${cur}%%${RESET} │ ${BOLD_CYAN}${PWD/#$HOME/~}${RESET} │ ${BRIGHT_WHITE}${model}${RESET} │ ${BRIGHT_WHITE}effort:${RESET} ${YELLOW}${effort}${RESET} │ ${branch_color}${branch}${git_dirty}${RESET} │ ${BRIGHT_WHITE}tokens in: ${RESET}${YELLOW}${in_fmt}${RESET} ${BRIGHT_WHITE}out: ${RESET}${YELLOW}${out_fmt}${RESET} │ ${GREEN}+${added}${RESET} ${RED}-${removed}${RESET}${section_rate}\n"
printf "${DIM}  ${offpeak_now} ${DIM}│ peak: Mon–Fri ${peak_start_il}:00–${peak_end_il}:00 IL${RESET}\n"
