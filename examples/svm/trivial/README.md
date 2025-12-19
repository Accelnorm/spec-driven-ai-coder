# SVM Trivial Example

A minimal Solana/Rust example for testing the AIComposer SVM workflow.

## Structure

- `src/lib.rs` - Main library with the `add` function
- `src/certora/spec/checks.rs` - CVLR specification with verification rule
- `system_doc.txt` - System documentation describing the component

## Rules

- `rule_add_is_correct` - Verifies that `add(x, y) == x + y`

## Usage

```bash
python main.py examples/svm/trivial/src/certora/spec/checks.rs \
    examples/svm/trivial/src/lib.rs \
    examples/svm/trivial/system_doc.txt \
    --target svm
```
