# Specification (written before implementation)

Actors: three distinct nonzero addresses: buyer, seller, arbiter. Fixed nonzero price in wei.

- Created: buyer can deposit exactly price once. Buyer and seller can each approve cancellation once; the second approval cancels the unfunded contract. Approvals do not prevent funding until both exist.
- Funded: buyer can release, or either buyer or seller can dispute. No cancellation after funding (as mandated by the required state machine).
- Disputed: arbiter alone chooses buyer or seller as the beneficiary.
- Cancelled, Released, ResolvedToBuyer, ResolvedToSeller: terminal states; no state-machine transitions.
- Released/resolved: credit a withdrawable balance rather than sending ETH inline. Recipient alone calls withdraw; state remains terminal.
- Invariant under normal calls: `address(this).balance == escrowed + totalPending`. Force-sent ETH is excluded from accounting.
- Liveness assumptions: the buyer must cooperate to release or a party must dispute; arbiter must be available after dispute; credited recipient must call withdraw. There is no timeout recovery.
- Scope: one escrow instance per deployment; no proxy, token support, fee or deadline.
