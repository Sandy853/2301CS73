# UTXO Ledger and Transaction Validator

Educational Bitcoin-like UTXO state machine using Python and maintained `cryptography` Ed25519 signatures. No mining, networking, or real coins. **Never use for real funds.**

## Files
- `ledger.py`: Outpoint, Output, Transaction, Wallet, validator, atomic state update, deterministic builder, JSON snapshot save/load.
- `demo.py`: prints accepted/rejected traces and writes JSON deliverables.
- `test_ledger.py`: 25+ automated `unittest` tests.
- `artifacts/`: sample ledger snapshots (`ledger_before.json`, `ledger_after.json`), signed payment, and `trace.json`.

## Setup / run
```bash
python -m pip install -r requirements.txt
python -m unittest -v
python demo.py
```
Run these commands from the project directory. `demo.py` creates/replaces files in `artifacts/`. It prints the trace and writes it to `artifacts/trace.json`.

## Design and validation
- Outpoint = `(transaction ID, output index)`. UTXO = positive 64-bit signed integer value and a SHA-256 hash of the raw 32-byte Ed25519 public key (toy P2PKH).
- Canonical serialization = UTF-8 JSON with lexicographically sorted keys, compact separators, ASCII escaping, and ordered input/output arrays. The transaction ID is SHA-256 of the **fully signed** canonical transaction JSON; signatures sign the canonical **unsigned** transaction JSON (all input references and all outputs). The same message is verified independently for every input.
- Validation rejects unsupported versions, missing/duplicate/spent inputs, unauthorized public keys, malformed/bad signatures, invalid output locks, zero/negative/noninteger/overflowing output values, sum overflow, and output totals greater than input totals.
- Fee = sum(inputs) - sum(outputs). Transaction acceptance constructs a new UTXO dictionary and replaces the old one only on complete success. In-memory atomicity assumes a single-threaded process (not concurrent/durable transactional storage).
- Coin selection: **largest-first**, deterministic tie-break `(txid, index)` ascending. Change = selected total - amount - fee, returned to the sender. If change is zero, no change output is created. A malformed change amount either fails value conservation or, if the fee is implicitly increased, is considered a different fee: the validator cannot infer a wallet's *intended* fee. Wallet-side tests check the exact requested change. No transaction-level fee field exists.
- `fund_for_demo` is a privileged test-only funding helper, outside transaction validation; there is no general coinbase/minting rule.
- Persistence: canonical JSON snapshots are saved via temporary file and `os.replace`; reload reconstructs identical logical outpoints and outputs. This is not a crash-safe database or authenticated snapshot format.

## Example
Alice's demo outputs are 40 and 70. The largest-first builder selects 70 then 40 and creates Bob=85, Alice change=23, fee=2. Replaying the signed transaction is rejected because its inputs were already spent. The trace records precise reasons and whether rejected attempts left the ledger unchanged.

## Scope / security
Keys exist in memory only; no private-key export. The wallet uses library-provided OS-backed randomness. This toy implementation omits script execution, blockchain consensus, chain reorgs, transaction malleability defenses, multi-party signing, concurrent access, and snapshot authentication. Do not interpret SHA-256(public key) as Bitcoin's HASH160.
