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

echo "=== Step 1: Generate CVLR manual from Certora Documentation ==="
$SCRIPT_DIR/gen_solana_docs.sh

if [[ ! -f "$SCRIPT_DIR/cvlr_manual.html" ]]; then
    echo "ERROR: cvlr_manual.html was not generated"
    exit 1
fi
echo "✅ cvlr_manual.html generated successfully"

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
python3 $SCRIPT_DIR/ragbuild_solana.py $SCRIPT_DIR/cvlr_manual.html

echo ""
echo "✅ Solana/CVLR RAG setup complete!"
echo ""
echo "The RAG database is now populated with CVLR documentation."
echo "You can use AI Composer with Solana specs."
