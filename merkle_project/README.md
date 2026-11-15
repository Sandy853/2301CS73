# Merkle Trees and Proofs of Inclusion

A Python standard-library-only SHA-256 Merkle tree library and CLI. No Merkle-tree package is used.

## Requirements

Python 3.10+; no third-party dependencies. `requirements.txt` is intentionally empty apart from a comment.

## Exact specification

- Leaves are **bytes**. The CLI reads UTF-8 transactions, **one line per transaction** (line endings removed). Blank lines count as empty transactions. An empty file means zero leaves.
- `Hleaf(data) = SHA256(0x00 || data)`.
- `Hnode(left, right) = SHA256(0x01 || left_32_bytes || right_32_bytes)`.
- For zero leaves, `root = SHA256(0x02)` (a distinct empty-tree domain).
- For one leaf, the root is its leaf hash, without adding a parent.
- At each level, if the number of nodes is odd and greater than one, **duplicate the last node**, hash it with itself, then continue. This rule applies again at higher levels.
- Proof `side` is the position of the **sibling** relative to the current hash, not the position of the current hash. For an odd duplicate, sibling side is `right` and its hash must equal the current hash.
- Proofs have exactly `ceil(log2(tree_size))` siblings for positive tree sizes (equivalently, the number of repeated `(n+1)//2` steps until `n==1`).
- All serialized hashes are exactly 64 **lowercase** hex characters. Verification rejects unknown fields, non-integer/bool indexes, out-of-range indexes, invalid directions, wrong-length proofs, malformed hashes, and incorrect duplicate hashes. It returns `false` for a well-formed proof whose computed root does not match.
- Proofs do not support an empty tree because there is no leaf to prove.

## Files

- `merkle.py` — library (`root`, `prove`, `verify`, `leaf_hash`, `node_hash`).
- `cli.py` — `root`, `prove`, `verify` CLI commands; `--output` saves JSON and all commands print results.
- `test_merkle.py` — unit tests including malformed-proof cases.
- `benchmark.py` — measures 8, 1,024, and 100,000 leaves.
- `generate_deliverables.py` — prints and saves test vectors, a five-transaction proof and path diagram, and performance results.
- `transactions.txt` — five example transactions.
- `deliverables/` — generated JSON and Markdown files.

## Run commands (from the project directory)

```bash
python -m unittest -v
python cli.py root --input transactions.txt --output deliverables/root_cli.json
python cli.py prove --input transactions.txt --index 2 --output deliverables/proof_cli.json
python cli.py verify --leaf tx2 --proof deliverables/proof_cli.json --root ROOT_HEX --output deliverables/verification.json
python generate_deliverables.py
python benchmark.py
```

Replace `ROOT_HEX` with the root printed by the `root` command (or copy the `root` value from `deliverables/root_cli.json`). `verify` exits 0 for valid, 1 for a well-formed but incorrect proof, and 2 for malformed input.

## Example five-transaction proof

For `tx0, tx1, tx2, tx3, tx4`, index 2 has **three** proof entries:

1. right: `Hleaf(tx3)`
2. left: `Hnode(Hleaf(tx0), Hleaf(tx1))`
3. right: `Hnode(C, C)`, where `C = Hnode(Hleaf(tx4), Hleaf(tx4))`

See `deliverables/proof_path_diagram.md` for the complete diagram and actual hex values. The two-sibling example in the assignment is illustrative only; it is insufficient under the specified duplicate-last policy for five leaves.

## Performance

Run `python benchmark.py` to print results and save `deliverables/performance.json` and `deliverables/performance_report.md`. Results depend on hardware. Root construction is O(n) time/memory, proof verification O(log n) time, proof length O(log n). This simple library rebuilds the tree when generating a proof, costing O(n) time; caching the levels could make repeated proof generation O(log n).
