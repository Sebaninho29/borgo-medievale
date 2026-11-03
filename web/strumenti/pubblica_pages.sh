#!/usr/bin/env bash
# Pubblica web/dist sul ramo gh-pages del repository (GitHub Pages, "Deploy from a branch": gh-pages, /).
# Il ramo contiene SOLO il sito compilato e un solo commit (si sovrascrive ogni volta con --force): la storia non
# accumula copie da ~55 MB. Uso (dalla cartella del progetto, dopo npm run build in web/):
#   bash web/strumenti/pubblica_pages.sh
# Da lanciare solo quando l'utente chiede di pubblicare.
set -euo pipefail
RADICE="$(cd "$(dirname "$0")/../.." && pwd)"
DIST="$RADICE/web/dist"
REMOTO="$(git -C "$RADICE" remote get-url origin)"
LIMITE=$((50 * 1024 * 1024))   # GitHub: avviso sopra 50 MB, blocco sopra 100 MB per file

[ -f "$DIST/index.html" ] || { echo "manca web/dist: prima npm run build in web/"; exit 1; }
grande="$(find "$DIST" -type f -size +$((LIMITE / 1024))k)"
[ -z "$grande" ] || { echo "file oltre 50 MB, non pubblico:"; echo "$grande"; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cp -r "$DIST"/. "$TMP"/
touch "$TMP/.nojekyll"          # niente Jekyll: i file si servono cosi' come sono
git -C "$TMP" init -q -b gh-pages
git -C "$TMP" config user.name "$(git -C "$RADICE" config user.name)"
git -C "$TMP" config user.email "$(git -C "$RADICE" config user.email)"
git -C "$TMP" add -A
git -C "$TMP" commit -q -m "Sito del borgo ($(date +%Y-%m-%d\ %H:%M))"
git -C "$TMP" push -q --force "$REMOTO" gh-pages
echo "pubblicato: $(du -sh "$DIST" | cut -f1), $(find "$DIST" -type f | wc -l) file"
