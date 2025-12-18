#!/bin/bash
set -e

# Setup script for Solana/CVLR RAG database
# This script generates the CVLR manual from the latest Certora Documentation
# and populates the RAG database with the documentation chunks.
#
# Prerequisites:
# - Docker compose running (see README.md for DB setup)
# - Python 3.11+
#
# Usage: ./setup_solana_rag.sh

SCRIPT_DIR=$(realpath $(dirname $0))

# Optional overrides:
# - Set SKIP_DOC_GEN=1 to skip regenerating cvlr_manual.html (useful if you edited it manually)
# - Set MANUAL_HTML=/absolute/or/relative/path/to/manual.html to use a specific manual

MANUAL_HTML=${MANUAL_HTML:-$SCRIPT_DIR/cvlr_manual.html}

echo "=== Step 1: Generate CVLR manual from Certora Documentation ==="
if [[ "${SKIP_DOC_GEN:-0}" == "1" ]]; then
    echo "Skipping doc generation (SKIP_DOC_GEN=1); using manual at: $MANUAL_HTML"
else
    $SCRIPT_DIR/gen_solana_docs.sh
fi

if [[ ! -f "$MANUAL_HTML" ]]; then
    echo "ERROR: manual not found at: $MANUAL_HTML"
    exit 1
fi
echo "✅ Manual found: $MANUAL_HTML"

echo ""
echo "=== Step 2: Setup RAG build environment ==="
RAG_VENV=$(mktemp -d)
cleanup() {
    echo "Cleaning up temporary venv..."
    rm -rf $RAG_VENV
}
trap cleanup EXIT

python3 -m venv $RAG_VENV
source $RAG_VENV/bin/activate
pip install -r $SCRIPT_DIR/rag_build_requirements.txt

echo ""
echo "=== Step 3: Build RAG database from CVLR manual ==="
python3 $SCRIPT_DIR/ragbuild_solana.py --reset "$MANUAL_HTML"

echo ""
echo "✅ Solana/CVLR RAG setup complete!"
echo ""
echo "The RAG database is now populated with CVLR documentation."
echo "You can use AI Composer with Solana specs."
