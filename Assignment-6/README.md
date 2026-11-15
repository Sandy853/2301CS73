# A Peer-to-Peer Mempool and Block Relay Network

An educational, **five-node localhost TCP** demonstration with framed JSON messages, inventory-first relay, toy Proof of Work, forks, reorganisation, mempool reconsideration, and structured logs. No third-party packages required.

## Run

```bash
python network.py --output deliverables --base-port 19000 --latency 0.02
```

Requires Python 3.10+ and five free consecutive localhost TCP ports. Run from the project directory. `requirements.txt` intentionally has no dependencies.

## Generated deliverables

- `deliverables/summary.txt`: printed and saved summary of final tips, heights, cumulative work, and mempool sizes.
- `deliverables/report.json`: machine-readable experiment assertions and per-node chain/mempool state.
- `deliverables/N0.jsonl` through `N4.jsonl`: timestamped structured logs with node ID, peer ID, object ID, and event.

## Protocol and experiment

Each TCP message is a 4-byte big-endian unsigned length followed by UTF-8 JSON, capped at 65,536 bytes. Messages have `v: 1` and one of: `hello`, `peers`, `inv`, `get`, `tx`, `block`, `ping`, `error`. Nodes exchange peer lists and inventory; missing objects are requested with `get`. Connections have 8-second read timeouts, a simple 100-message/second per-peer limit, error handling and peer scores. Duplicate transactions are suppressed; the mempool checks sender balances/nonces, fee replacement for same sender/nonce, and 120-second expiry on insertion. Transactions are ordered by fee (a stand-in for fee rate because this toy format has no variable-size transaction serialization).

The demo partitions N0/N1 from N2/N3/N4. Both sides mine competing height-one blocks, then N3 mines a second block. After healing, the nodes request the missing blocks and adopt the longer **most-work** branch. The stale block's Alice-to-Bob transaction is returned to each mempool if still valid. The program asserts convergence and restoration, failing visibly if either does not happen.

## Scope and limitations

This is a **standalone educational model**, not an automatic import of Assignment 5. For direct integration, replace `valid_tx`, `apply_block`, `merkle`, and the toy mining functions with the corresponding Assignment 5 validator and block classes. Transactions use simple account balances/nonces rather than UTXOs, and have no signatures. Coinbase is represented as a block reward field. The fixed difficulty target means most-work and height agree in this experiment; cumulative work is still explicitly tracked. The network uses an in-process controller to create five genuine TCP servers. It is not secure against malicious participants or suitable for production. Peers are discovered from handshake lists, but the experiment pre-connects its full mesh. The rate limiter is per identified peer and is not an IP-based anti-DoS defense.
