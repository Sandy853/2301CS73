# Blocks, Proof of Work, Forks, and Reorganisation

An educational Python blockchain with Ed25519-authorized UTXO spends, toy proof of work, fork tracking, and **most cumulative work** chain selection. No networking or real-world mining.

## Setup

Python 3.10+:

```bash
python -m pip install -r requirements.txt
python demo.py
python demo.py mine --target-bits 8
python demo.py benchmark
python -m unittest discover -v
```

Run from the project directory. `demo.py` prints accepted/rejected block decisions, UTXOs, fork diagram, block-header hex, and benchmark summary. It writes all JSON and text artifacts into `artifacts/`.

## Files

- `blockchain.py`: block header, canonical JSON transaction IDs, Merkle tree, Ed25519 P2PKH-like locking, transaction validator, mining, branch-specific state, cumulative work, and chain manager.
- `demo.py`: node-local fork simulation, miner command, benchmark, and report artifact generation.
- `test_blockchain.py`: automated validation and reorganisation tests.
- `artifacts/`: generated snapshots, trace, fork diagram, block header, and PoW measurements.

## Consensus and validation rules

Header serialization (116 bytes): 4-byte little-endian version; 32-byte previous hash; 32-byte Merkle root; 8-byte little-endian timestamp; 32-byte big-endian target; 8-byte little-endian nonce. The block hash is SHA-256 of these bytes; valid PoW means `int(hash,16) <= target`. Toy work is `floor(2^256 / (target+1))`. Targets are selected per block, bounded by node's `max_target` (toy policy, **not** Bitcoin retargeting). The highest cumulative work valid branch wins; ties preserve the current active tip.

Transactions use sorted-key compact JSON, SHA-256 txids, Merkle hashes with odd-leaf duplication, and Ed25519 signatures of unsigned inputs/outputs. Outputs lock to SHA-256(public key). Coinbase must be first, unique, and have correct height; value must not exceed subsidy (50) plus block fees. Each spend checks outpoint existence, uniqueness, ownership, signatures, nonnegative bounded values, sum overflow, and conservation of value. Intra-block spends are applied in order. **No coinbase maturity rule** in this toy model.

Each accepted block stores a validated **branch-specific UTXO snapshot**. A reorganisation switches the active tip to the higher-work branch's snapshot, which is logically equivalent to disconnecting the losing branch (restoring spent outputs) and connecting the winning branch. The reorg event explicitly lists disconnected and connected hashes. Invalid blocks never mutate the chain manager. This is memory-heavy but straightforward and safe for a small demonstration.

## Fork example

The demo mines a genesis block, then Miner A extends a branch by two easy blocks. Miner B mines one harder competing block from genesis. Because Miner B's block contributes more work than both of Miner A's blocks, Miner B wins despite having fewer blocks. Alice's spent genesis output is restored if her spend occurred only on Miner A's losing branch.

## Expected vs observed mining attempts

A uniformly random 256-bit hash succeeds with probability `(target+1)/2^256`, giving expected attempts `2^256/(target+1)`. The benchmark tests three toy targets `MAX_HASH >> 4`, `>> 6`, and `>> 8` (roughly 16, 64, 256 expected attempts). Each uses five trials; observed attempts and hashes/second are measured at runtime and saved to `artifacts/benchmark.json`. Small samples fluctuate substantially.

## Artifacts

- `ledger_before.json`, `ledger_before_reorg.json`, `ledger_after_reorg.json`
- `trace.json` with exact acceptance/rejection reasons
- `fork_events.json` with disconnect/connect lists
- `fork_diagram.txt` (ASCII competing branches)
- `block_header.json` with 116-byte header hex dump
- `benchmark.json` with three targets, five trials each, measured hashes/sec and expected/observed attempts
- `mined_block.json` when using the `mine` command

## Limitations

Educational design only: no networking, mempool, persistence of chain database, timestamp drift checks, difficulty adjustment, coinbase maturity, transaction size limits, or Bitcoin-compatible signatures/serialization. The block header commits to the full transaction Merkle tree, including witnesses. Keys are generated only for temporary demo use and never written to disk.
