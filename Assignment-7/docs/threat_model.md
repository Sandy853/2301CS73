# Threat model

| Threat | Mitigation / residual risk |
|---|---|
| Unauthorized release or resolution | `onlyBuyer`, `onlyArbiter` and state guards |
| Seller/buyer/arbiter collusion | Three distinct addresses; collusion between people cannot be prevented |
| Double funding or double payout | Exact-value funding in Created only; zero pending before external transfer |
| Reentrancy | Checks-effects-interactions and nonReentrant on withdraw |
| Refusing to accept ETH | Withdrawal reverts without destroying credit; recipient may remain unable to collect if it rejects ETH |
| Arbiter disappears | Dispute funds can remain locked indefinitely; production design needs bounded recovery |
| Buyer disappears without disputing | Funded escrow can remain locked; production design needs deadlines or mutual funded cancellation |
| Force-sent ETH | Forced ETH can make raw balance exceed liabilities; no sweep provided |
| Private key compromise | Out of scope; deploy with trusted, separately controlled accounts |
| Miner/MEV ordering | Funding vs second cancellation approval can race; normal ordering decides winner |
| Chain reorg | Local test finality not mainnet finality |

**Important:** The specification requires `Funded` to transition only to `Released` or `Disputed`. Consequently, a funded escrow cannot be mutually cancelled, and liveness relies on the parties and arbiter. A production escrow should explicitly revise the state machine to add time-bounded recovery or a funded mutual-refund path.
