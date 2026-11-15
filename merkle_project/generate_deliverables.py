"""Print and save example roots, test vectors, inclusion proof, diagram and benchmarks."""
import json
from pathlib import Path
from merkle import root, prove, verify, leaf_hash, node_hash
from benchmark import run


def main():
    out = Path('deliverables')
    out.mkdir(exist_ok=True)
    examples = {str(n): [f'tx{i}'.encode() for i in range(n)] for n in (0, 1, 4, 5)}
    vectors = []
    for label, leaves in examples.items():
        r = root(leaves)
        item = {'tree_size': len(leaves), 'transactions': [x.decode() for x in leaves], 'root': r}
        if leaves:
            i = 2 if len(leaves) == 5 else len(leaves) - 1
            item['proof_index'] = i
            item['proof'] = prove(leaves, i)
            item['verified'] = verify(leaves[i], item['proof'], r)
        vectors.append(item)
    (out / 'test_vectors.json').write_text(json.dumps(vectors, indent=2) + '\n')
    leaves = examples['5']
    proof = prove(leaves, 2)
    (out / 'proof_tx2.json').write_text(json.dumps(proof, indent=2) + '\n')
    (out / 'root_5.json').write_text(json.dumps({'tree_size': 5, 'root': root(leaves)}, indent=2) + '\n')
    # Exact five-transaction path for index 2: h2 + h3 -> B; A + B -> D; D + E -> ROOT.
    h = [leaf_hash(x) for x in leaves]
    A = node_hash(h[0], h[1]); B = node_hash(h[2], h[3]); C = node_hash(h[4], h[4])
    D = node_hash(A, B); E = node_hash(C, C)
    diagram = f'''# Five-transaction inclusion proof (index 2: tx2)

```text
                            ROOT = Hnode(D, E)
                           /                  \\
                  D = Hnode(A, B)        E = Hnode(C, C)
                  /            \\          /             \\
          A=Hnode(h0,h1)   B=Hnode(h2,h3)  C             C (duplicate)
           /      \\         /      \\      / \\
          h0      h1       [h2]     h3    h4  h4 (duplicate)
          tx0     tx1       tx2      tx3   tx4

Proof path for tx2:
  level 0: h3 is RIGHT sibling of h2
  level 1: A  is LEFT  sibling of B
  level 2: E  is RIGHT sibling of D
```

Proof hashes (hex):
- h3 = `{h[3].hex()}`
- A  = `{A.hex()}`
- E  = `{E.hex()}`

Root = `{root(leaves)}`

Note: odd nodes are duplicated at EVERY level. For 5 leaves, h4 is duplicated into C, then C is duplicated into E. The proof for tx2 therefore contains **three** siblings, not two.
'''
    (out / 'proof_path_diagram.md').write_text(diagram)
    print('TEST VECTORS:')
    print(json.dumps(vectors, indent=2))
    print('\nFIVE-LEAF PROOF PATH:\n' + diagram)
    run(str(out))
    print('\nSaved deliverables in:', out.resolve())


if __name__ == '__main__':
    main()
