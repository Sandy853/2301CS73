# Proof of Work, Forks and Reorganisation — Demo Report

## Block header hex dump

Header length: 116 bytes (232 hexadecimal characters).

```text
010000000182eb1daa4b1922d0d43e1208ed59ff897c9bc70eda6f39838122801191dbd3cf3af7bf1165d2d111567be5729d8a9bdb23cb637ea2ce962af4d3e5b467657ad0ebf96a0000000000ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff1001000000000000
```

Block hash: `003903ab5e0237fa4afb4b0e715ecc04217a8f51f14be3e3db91497b035cc431`

## Competing branches

```text
Competing branches (each arrow points from parent to child):
GENESIS 0182eb1daa4b (work 32)
  |-- Miner A: 04e141fc4dd2 -> 04b9c03e3aa2  (2 blocks, branch work 64) [LOST]
  `-- Miner B: 003903ab5e02  (1 block, branch work 256) [ACTIVE]
Reorg: disconnect A2, A1; connect B1. Bob's old output is removed; Alice's new output appears.
```

## PoW measurements

| Target shift | Expected attempts | Observed mean attempts | Mean hashes/sec |
|---|---:|---:|---:|
| 4 | 16.0 | 29.8 | 570212 |
| 6 | 64.0 | 82.6 | 564732 |
| 8 | 256.0 | 308.6 | 592802 |

Five independent trials per target; actual results depend on the machine and random-looking header hashes.

## Validation trace

| Scenario | Result | Reason |
|---|---|---|
| genesis | accepted | valid block |
| miner A: low-work block 1 | accepted | valid block |
| miner A: low-work block 2 | accepted | valid block |
| miner B: shorter higher-work fork | accepted | valid block |
| duplicate block | rejected | duplicate block |
| incorrect Merkle root | rejected | incorrect Merkle root |
| excess coinbase | rejected | excess coinbase value |
| invalid transaction | rejected | missing or already spent input: ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff:0 |
| invalid proof of work | rejected | invalid proof of work |

## Reorganisation verification

The winning branch is shorter but has more cumulative work. Its branch-specific UTXO snapshot replaces the previous active snapshot; outputs from disconnected blocks are no longer active, and the winning branch’s outputs are present. All rejected blocks leave active state unchanged.
