#!/usr/bin/env bash
# Remove everything install.sh created. Saved games and best times are kept
# unless --purge is passed.
set -euo pipefail

bin_dir="${XDG_BIN_HOME:-$HOME/.local/bin}"
apps_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
icon_dir="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/omarchysweep"

rm -f "$bin_dir/omarchysweep" "$apps_dir/OmarchySweep.desktop" "$icon_dir/omarchysweep.svg"
command -v update-desktop-database >/dev/null && update-desktop-database -q "$apps_dir" || true

if [[ ${1:-} == --purge ]]; then
  rm -rf "$state_dir"
  echo "Removed OmarchySweep and its saved best times."
else
  echo "Removed OmarchySweep. Best times kept in $state_dir (--purge to delete)."
fi
