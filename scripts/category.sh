#!/bin/bash
# Wrapper for desktop Action menu: toggle/start/stop/status sections by category.
# Usage: category.sh {ai|media|ebooks|asf|all} {toggle|up|down|status}

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOME_SERVER_DIR="$(dirname "$SCRIPT_DIR")"

CATEGORY="${1:-}"
ACTION="${2:-toggle}"

case "$CATEGORY" in
    ai)     sections=(forge sillytavern) ;;
    media)  sections=(media) ;;
    ebooks) sections=(ebooks) ;;
    asf)    sections=(asf) ;;
    all)    sections=(dashboard forge sillytavern media ebooks asf) ;;
    *)
        echo "Usage: $0 {ai|media|ebooks|asf|all} {toggle|up|down|status}"
        exit 1
        ;;
esac

section_container() {
    case "$1" in
        forge|sillytavern|dashboard|asf) echo "home-$1" ;;
        ebooks) echo "home-ebooks" ;;
        media) echo "jellyfin" ;;
    esac
}

is_section_up() {
    podman ps --filter "name=$(section_container "$1")" --format "{{.Names}}" | grep -q .
}

count_up() {
    local up=0
    for s in "${sections[@]}"; do
        is_section_up "$s" && up=$((up + 1))
    done
    echo "$up"
}

notify() {
    # $1=summary $2=body $3=urgency(low|normal|critical) $4=icon
    notify-send -a "Home Server" --expire-time=4000 \
        ${3:+-u "$3"} ${4:+-i "$4"} \
        "$1" "${2:-}" 2>/dev/null || true
}

# Status mode: report current state of category
if [[ "$ACTION" == "status" ]]; then
    body=""
    for s in "${sections[@]}"; do
        if is_section_up "$s"; then
            body="${body}● ${s}: ON\n"
        else
            body="${body}○ ${s}: off\n"
        fi
    done
    up=$(count_up)
    total=${#sections[@]}
    if (( up == total )); then
        notify "${CATEGORY^}: all ON ($up/$total)" "$(echo -e "$body")" normal "dialog-information"
    elif (( up == 0 )); then
        notify "${CATEGORY^}: all OFF (0/$total)" "$(echo -e "$body")" low "dialog-information"
    else
        notify "${CATEGORY^}: partial ($up/$total)" "$(echo -e "$body")" normal "dialog-warning"
    fi
    exit 0
fi

# Toggle: detect state and pick action
if [[ "$ACTION" == "toggle" ]]; then
    up=$(count_up)
    total=${#sections[@]}
    if (( up == total )); then ACTION="down"; else ACTION="up"; fi
fi

cd "$HOME_SERVER_DIR"

# Reverse order for shutdown
if [[ "$ACTION" == "down" ]]; then
    reversed=()
    for ((i=${#sections[@]}-1; i>=0; i--)); do reversed+=("${sections[i]}"); done
    sections=("${reversed[@]}")
fi

# Pre-action notification — show what's happening
verb_now="Starting"; verb_done="ON"; icon="media-playback-start"
if [[ "$ACTION" == "down" ]]; then verb_now="Stopping"; verb_done="OFF"; icon="media-playback-stop"; fi

notify "${verb_now} ${CATEGORY}..." "" normal "$icon"

failed=()
for s in "${sections[@]}"; do
    if [[ "$ACTION" == "up" ]]; then
        ./scripts/up.sh "$s" >/dev/null 2>&1 || failed+=("$s")
    else
        ./scripts/down.sh "$s" >/dev/null 2>&1 || failed+=("$s")
    fi
done

# Post-action notification — show resulting state
final_up=$(count_up)
final_total=${#sections[@]}

if [[ ${#failed[@]} -eq 0 ]]; then
    notify "✓ ${CATEGORY^} is now ${verb_done}" "${final_up}/${final_total} services" normal "$icon"
else
    notify "✗ ${CATEGORY^}: ${verb_done} partial (${final_up}/${final_total})" \
        "Failed: ${failed[*]} — debug: ./scripts/${ACTION}.sh ${failed[0]}" \
        critical "dialog-error"
fi
