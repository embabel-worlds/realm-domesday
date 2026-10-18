#!/usr/bin/env bash
#
# Rebuilds reference/ from the Hull Domesday Explorer database.
#
# The Explorer is a 2002 Windows program whose data is Paradox tables plus a word-coded text
# store. Its v1.1 update, published by the Hull Domesday Project, carries the whole database;
# this downloads it once into .cache/, converts the tables with pdxreader, decodes the text
# store, parses the manorial figures and writes the YAML the appliance seeds.
#
# pdxreader is built from source at a pinned commit: the release on Maven Central (1.6)
# misreads Paradox numbers and loses records from part-full blocks, and the fix
# (teverett/paradoxReader#171) is not released yet. Move PDXREADER_COMMIT to a release when
# there is one.
#
# Needs: curl, unzip, git, mvn, java 17+, python 3.10+.
set -euo pipefail
cd "$(dirname "$0")/.."

CACHE=.cache
PDXREADER_REPO=https://github.com/johnsonr/paradoxReader.git
PDXREADER_COMMIT=d1cfb7b
EXPLORER_ZIP_ID=0B4ZNjiJo0-QDUXlEMTB6OGlIdkE
EXPLORER_ZIP_KEY=0-BWz9QlhwTU-dhMgPeXyA0Q
MAVEN=https://repo1.maven.org/maven2

mkdir -p "$CACHE"

if [ ! -d "$CACHE/explorer/Databases" ]; then
  curl -fsSL -o "$CACHE/DomesdayExplorer1.1.zip" \
    "https://drive.usercontent.google.com/download?id=$EXPLORER_ZIP_ID&resourcekey=$EXPLORER_ZIP_KEY&export=download&confirm=t"
  unzip -q -o "$CACHE/DomesdayExplorer1.1.zip" -d "$CACHE/explorer"
fi

if [ ! -f "$CACHE/pdxreader.jar" ]; then
  rm -rf "$CACHE/paradoxReader"
  git clone -q "$PDXREADER_REPO" "$CACHE/paradoxReader"
  git -C "$CACHE/paradoxReader" checkout -q "$PDXREADER_COMMIT"
  (cd "$CACHE/paradoxReader" && mvn -q -B -DskipTests package)
  cp "$CACHE"/paradoxReader/target/pdxreader-*-SNAPSHOT.jar "$CACHE/pdxreader.jar"
  curl -fsSL -o "$CACHE/commons-csv.jar" "$MAVEN/org/apache/commons/commons-csv/1.14.1/commons-csv-1.14.1.jar"
  curl -fsSL -o "$CACHE/commons-codec.jar" "$MAVEN/commons-codec/commons-codec/1.19.0/commons-codec-1.19.0.jar"
fi

CP="$CACHE/pdxreader.jar:$CACHE/commons-csv.jar:$CACHE/commons-codec.jar"
rm -rf "$CACHE/csv"
java -cp "$CP" scripts/convert/Convert.java "$CACHE/explorer/Databases" "$CACHE/explorer/Textbase" "$CACHE/csv"

if [ ! -d "$CACHE/venv" ]; then
  python3 -m venv "$CACHE/venv"
  "$CACHE/venv/bin/pip" -q install -r scripts/requirements.txt
fi
"$CACHE/venv/bin/python" scripts/decode_textbase.py "$CACHE"
"$CACHE/venv/bin/python" scripts/build_reference.py "$CACHE"
