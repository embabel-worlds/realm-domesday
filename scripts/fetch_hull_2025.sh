#!/usr/bin/env bash
#
# Downloads Hull's 2025 Domesday deposit into .cache/hull2025/: the translation, which carries
# Little Domesday (Essex, Norfolk, Suffolk), and whatever database and documentation files the
# repository will name.
#
# Hull's repository (digitalcollections.hull.ac.uk, Hyrax behind Cloudflare) serves files from
# /downloads/<file-set id> without a challenge, but the work pages that name those ids
# (/concern/datasets/<id>) are challenged, and a script cannot pass the challenge. The
# translation's file-set id is known and fixed here; for every other item this asks for the work
# page once, and if it is refused, says so and moves on rather than retrying until it is let in.
# A file-set id found by hand can be given in HULL_FILESETS ("id:name id:name") and is fetched
# like the translation.
#
# Politeness is the point of the shape: a browser User-Agent (the site refuses others), at least
# five seconds between requests, and on a 429 ninety seconds' wait, at most three times.
#
# Re-runnable: a file already downloaded is not fetched again. SKIP_ITEMS=1 leaves the work pages
# alone, for when Cloudflare is known to be challenging them.
set -euo pipefail
cd "$(dirname "$0")/.."

OUT=.cache/hull2025
SITE=https://digitalcollections.hull.ac.uk
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
TRANSLATION_FILESET=h989r387g

# Work ids: the seven databases, the readme, and the documentation items.
DATABASES="7s75dc929 3b591903d k0698797c mp48sd31z qv33rx26p 3n203z60c fn106z48v"
README=sx61dm99v
DOCUMENTATION="p5547r99h j6731423d fx719m879 nk322d937 9593tv75c v405s9956 3f4625912 1j92g800d cv43nx46d 8g84mm94q 6108vb88w ff365582v"

mkdir -p "$OUT/pages" "$OUT/files"

# get URL FILE: one polite request; prints the HTTP status.
get() {
  local code tries=0
  while :; do
    code=$(curl -sS -L -A "$UA" -H 'Accept: text/html,application/xhtml+xml,*/*;q=0.8' \
      -H 'Accept-Language: en-GB,en;q=0.9' -o "$2" -w '%{http_code}' "$1" || echo 000)
    sleep 5
    if [ "$code" = 429 ] && [ $tries -lt 3 ]; then
      tries=$((tries + 1))
      echo "  429 from $1; waiting 90s ($tries/3)" >&2
      sleep 90
      continue
    fi
    echo "$code"
    return
  done
}

challenged() { grep -q '<title>Just a moment' "$1" 2>/dev/null; }

# fetch_fileset ID NAME: a file by its file-set id, named as the server names it when NAME is empty.
fetch_fileset() {
  local id=$1 name=${2:-} tmp="$OUT/files/.$1.part"
  if ls "$OUT/files/$id"--* >/dev/null 2>&1; then
    echo "  have $(ls "$OUT/files/$id"--* | head -1)"
    return
  fi
  local headers code
  headers=$(curl -sS -A "$UA" -D - -o "$tmp" -w '\n%{http_code}' "$SITE/downloads/$id" || true)
  sleep 5
  code=$(printf '%s' "$headers" | tail -1)
  if [ "$code" != 200 ]; then
    echo "  /downloads/$id: HTTP $code (a 302 is a login redirect: the file is not public)"
    rm -f "$tmp"
    return
  fi
  [ -n "$name" ] || name=$(printf '%s' "$headers" | grep -i '^content-disposition:' | sed 's/.*filename="\([^"]*\)".*/\1/' | head -1)
  mv "$tmp" "$OUT/files/$id--${name:-content}"
  echo "  saved $OUT/files/$id--${name:-content}"
}

echo "translation (h989r385x)"
fetch_fileset "$TRANSLATION_FILESET" translation.txt
# little_domesday.py reads .cache/hull_translation.txt when the build has put it there, and this
# copy otherwise
cp -n "$OUT/files/$TRANSLATION_FILESET--translation.txt" "$OUT/translation.txt" 2>/dev/null || true

for c in 3t945r28b dz010q52k r494vk876; do
  [ -s "$OUT/pages/collection-$c.json" ] || echo "collection $c: HTTP $(get "$SITE/collections/$c.json" "$OUT/pages/collection-$c.json")"
done

refused=""
# SKIP_ITEMS=1 fetches only the translation and the collections, sending no work-page requests
[ -n "${SKIP_ITEMS:-}" ] && DATABASES="" README="" DOCUMENTATION=""
for id in $DATABASES $README $DOCUMENTATION; do
  page="$OUT/pages/$id.html"
  if [ ! -s "$page" ] || challenged "$page"; then
    echo "item $id: HTTP $(get "$SITE/concern/datasets/$id?locale=en" "$page")"
  fi
  if challenged "$page"; then
    refused="$refused $id"
    continue
  fi
  for fs in $(grep -o '/downloads/[a-z0-9]\{9\}' "$page" | sort -u | sed 's|/downloads/||'); do
    fetch_fileset "$fs"
  done
done

for pair in ${HULL_FILESETS:-}; do
  fetch_fileset "${pair%%:*}" "${pair#*:}"
done

if [ -n "$refused" ]; then
  echo
  echo "Cloudflare challenged these work pages, so their files could not be named:$refused"
  echo "Open one in a browser, note each '/downloads/<id>' link, and re-run with"
  echo "  HULL_FILESETS='<id>:<filename> ...' $0"
fi
