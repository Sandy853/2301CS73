"""Run: python demo.py [demo|mine|benchmark] [--target-bits N]"""
import argparse, json
from pathlib import Path
from blockchain import *

ART = Path('artifacts')
def run_demo():
    alice, alice_pk = keypair(); bob, bob_pk = keypair(); miner, miner_pk = keypair()
    a, b, m = address(alice_pk), address(bob_pk), address(miner_pk)
    node = Node()
    target_easy = MAX_HASH >> 5   # expected ~32 attempts
    target_hard = MAX_HASH >> 8   # expected ~256 attempts
    trace = []
    def add(block, name):
        before = snapshot(node)
        try:
            result = node.add(block)
            trace.append({'name': name, 'status': 'accepted', **result})
            print(f"ACCEPTED {name}: height={result['height']}, active={result['active']}, work={result['cumulative_work']}")
        except ValidationError as exc:
            assert snapshot(node) == before
            trace.append({'name': name, 'status': 'rejected', 'reason': str(exc)})
            print(f'REJECTED {name}: {exc}')
    genesis, _ = mine(ZERO, [coinbase(a, 50, 0, 'genesis')], target_easy)
    add(genesis, 'genesis')
    save_json(ART/'ledger_before.json', snapshot(node))
    # Alice spends genesis coinbase in competing blocks. Both spend the same outpoint on different branches.
    inp = [{'txid': txid(genesis.transactions[0]), 'index': 0}]
    pay_bob = make_spend(inp, [output(30, b), output(18, a)], [alice])
    pay_alice = make_spend(inp, [output(45, a)], [alice])
    low1, _ = mine(genesis.hash(), [coinbase(m, 52, 1, 'miner-low-1'), pay_bob], target_easy)
    add(low1, 'miner A: low-work block 1')
    low2, _ = mine(low1.hash(), [coinbase(m, 50, 2, 'miner-low-2')], target_easy)
    add(low2, 'miner A: low-work block 2')
    save_json(ART/'ledger_before_reorg.json', snapshot(node))
    high1, _ = mine(genesis.hash(), [coinbase(m, 55, 1, 'miner-high-1'), pay_alice], target_hard)
    add(high1, 'miner B: shorter higher-work fork')
    save_json(ART/'ledger_after_reorg.json', snapshot(node))
    assert node.tip == high1.hash()
    assert f'{txid(pay_bob)}:0' not in node.utxos()
    assert f'{txid(pay_alice)}:0' in node.utxos()
    add(high1, 'duplicate block')
    bad_merkle, _ = mine(high1.hash(), [coinbase(m, 50, 2, 'bad-root')], target_easy)
    bad_merkle.header.merkle_root = ZERO
    add(bad_merkle, 'incorrect Merkle root')
    bad_coinbase, _ = mine(high1.hash(), [coinbase(m, 51, 2, 'excess')], target_easy)
    add(bad_coinbase, 'excess coinbase')
    bad_tx = make_spend([{'txid': 'ff'*32, 'index': 0}], [output(1,b)], [alice])
    bad_block, _ = mine(high1.hash(), [coinbase(m, 50, 2, 'bad-tx'), bad_tx], target_easy)
    add(bad_block, 'invalid transaction')
    bad_pow, _ = mine(high1.hash(), [coinbase(m, 50, 2, 'bad-pow')], target_easy)
    bad_pow.header.nonce = next(n for n in range(100000) if int(Header(1, high1.hash(), bad_pow.header.merkle_root, bad_pow.header.timestamp, target_easy, n).hash(),16)>target_easy)
    add(bad_pow, 'invalid proof of work')
    save_json(ART/'trace.json', trace)
    save_json(ART/'fork_events.json', node.events)
    save_json(ART/'block_header.json', {'header': high1.header.as_dict(), 'header_hex': high1.header.encode().hex(), 'hash': high1.hash(), 'work': work(target_hard)})
    diagram = f'''Competing branches (each arrow points from parent to child):
GENESIS {genesis.hash()[:12]} (work {work(target_easy)})
  |-- Miner A: {low1.hash()[:12]} -> {low2.hash()[:12]}  (2 blocks, branch work {2*work(target_easy)}) [LOST]
  `-- Miner B: {high1.hash()[:12]}  (1 block, branch work {work(target_hard)}) [ACTIVE]
Reorg: disconnect A2, A1; connect B1. Bob's old output is removed; Alice's new output appears.
'''
    (ART/'fork_diagram.txt').write_text(diagram)
    print('\n'+diagram)
    print('Block header hex:', high1.header.encode().hex())
    print('Final UTXOs:', json.dumps(node.utxos(), indent=2))
    print('Saved outputs to:', ART.resolve())
    return node

def benchmark():
    _, pk = keypair(); addr = address(pk)
    results = []
    for bits in (4, 6, 8):
        target = MAX_HASH >> bits
        for trial in range(5):
            block, metrics = mine(ZERO, [coinbase(addr, 50, 0, f'benchmark-{bits}-{trial}')], target)
            results.append({'target_bits': bits, 'target_hex': f'{target:064x}', 'trial': trial+1, 'hash': block.hash(), **metrics})
    save_json(ART/'benchmark.json', results)
    print('Toy PoW benchmark (5 trials per target):')
    for bits in (4, 6, 8):
        rows = [r for r in results if r['target_bits'] == bits]
        print(f"bits={bits}, expected attempts={rows[0]['expected_attempts']:.1f}, observed mean={sum(r['attempts'] for r in rows)/len(rows):.1f}, mean hashes/sec={sum(r['hashes_per_second'] for r in rows)/len(rows):.0f}")
    return results

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('command', nargs='?', choices=['demo','mine','benchmark'], default='demo')
    p.add_argument('--target-bits', type=int, default=8)
    args = p.parse_args()
    if args.command == 'demo': run_demo(); benchmark()
    elif args.command == 'benchmark': benchmark()
    else:
        if not 1 <= args.target_bits <= 20: p.error('--target-bits must be between 1 and 20')
        _, pk = keypair()
        b, stats = mine(ZERO, [coinbase(address(pk), SUBSIDY, 0, 'cli-miner')], MAX_HASH >> args.target_bits)
        print(json.dumps({'block': b.as_dict(), 'header_hex': b.header.encode().hex(), 'stats': stats}, indent=2))
        save_json(ART/'mined_block.json', {'block': b.as_dict(), 'stats': stats})
