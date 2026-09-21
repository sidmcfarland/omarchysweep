#!/usr/bin/env bash
# Install OmarchySweep for the current user: launcher on PATH, menu entry, icon.
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
bin_dir="${XDG_BIN_HOME:-$HOME/.local/bin}"
apps_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
icon_dir="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"

mkdir -p "$bin_dir" "$apps_dir" "$icon_dir"

ln -sf "$root/bin/omarchysweep" "$bin_dir/omarchysweep"
install -m 644 "$root/icons/omarchysweep.svg" "$icon_dir/omarchysweep.svg"

# Point the menu entry at the launcher itself, so it works whether or not
# ~/.local/bin is on the session PATH.
sed "s|-e omarchysweep$|-e $bin_dir/omarchysweep|" \
  "$root/applications/OmarchySweep.desktop" >"$apps_dir/OmarchySweep.desktop"
chmod 644 "$apps_dir/OmarchySweep.desktop"

command -v update-desktop-database >/dev/null && update-desktop-database -q "$apps_dir" || true
command -v gtk-update-icon-cache >/dev/null &&
  gtk-update-icon-cache -qtf "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor" 2>/dev/null || true

echo "OmarchySweep installed."
echo "  run:   omarchysweep            (or search 'OmarchySweep' in the Omarchy menu)"
echo "  keys:  arrows move, f flags, d digs, o for grid size and difficulty"

case ":$PATH:" in
  *":$bin_dir:"*) ;;
  *) echo "  note:  $bin_dir is not on your PATH yet" ;;
esac
