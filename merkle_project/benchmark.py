"""Benchmark deterministic transaction sets; save JSON and Markdown reports."""
import json
import statistics
import time
from pathlib import Path
from merkle import root, prove, verify


def run(output_dir='deliverables'):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for size in (8, 1024, 100000):
        leaves = [f'transaction-{i:06d}'.encode() for i in range(size)]
        times = []
        for _ in range(3):
            start = time.perf_counter()
            r = root(leaves)
            times.append((time.perf_counter() - start) * 1000)
        index = size // 2
        start = time.perf_counter()
        proof = prove(leaves, index)
        proof_ms = (time.perf_counter() - start) * 1000
        assert verify(leaves[index], proof, r)
        serialized = json.dumps(proof, separators=(',', ':'), ensure_ascii=False).encode()
        rows.append({'leaves': size, 'root': r, 'construction_ms_median': round(statistics.median(times), 3),
                     'proof_generation_ms': round(proof_ms, 3), 'proof_hashes': len(proof['siblings']),
                     'proof_json_bytes': len(serialized)})
        print(f'{size:>7} leaves | build {statistics.median(times):>9.3f} ms | proof {len(serialized):>5} bytes | siblings {len(proof["siblings"])}')
    (out / 'performance.json').write_text(json.dumps(rows, indent=2) + '\n')
    lines = ['# Performance report', '', 'SHA-256, duplicate-last, deterministic UTF-8 transactions; median of three root constructions. Timings vary by machine.', '',
             '| Leaves | Root construction (ms) | Proof generation (ms) | Sibling hashes | Compact proof JSON (bytes) |',
             '|---:|---:|---:|---:|---:|']
    for x in rows:
        lines.append(f'| {x["leaves"]:,} | {x["construction_ms_median"]:.3f} | {x["proof_generation_ms"]:.3f} | {x["proof_hashes"]} | {x["proof_json_bytes"]} |')
    lines += ['', 'Construction is O(n) time and O(n) memory; proof has O(log n) hashes. Proof generation here rebuilds the tree, so it takes O(n) time. Verification takes O(log n) time and O(1) auxiliary space.', '']
    (out / 'performance_report.md').write_text('\n'.join(lines))
    print('Saved performance.json and performance_report.md')


if __name__ == '__main__':
    run()
