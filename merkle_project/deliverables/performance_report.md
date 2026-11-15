# Performance report

SHA-256, duplicate-last, deterministic UTF-8 transactions; median of three root constructions. Timings vary by machine.

| Leaves | Root construction (ms) | Proof generation (ms) | Sibling hashes | Compact proof JSON (bytes) |
|---:|---:|---:|---:|---:|
| 8 | 0.031 | 0.033 | 3 | 315 |
| 1,024 | 1.801 | 1.774 | 10 | 957 |
| 100,000 | 217.238 | 511.447 | 17 | 1593 |

Construction is O(n) time and O(n) memory; proof has O(log n) hashes. Proof generation here rebuilds the tree, so it takes O(n) time. Verification takes O(log n) time and O(1) auxiliary space.
