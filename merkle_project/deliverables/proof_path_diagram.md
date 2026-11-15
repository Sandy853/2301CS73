# Five-transaction inclusion proof (index 2: tx2)

```text
                            ROOT = Hnode(D, E)
                           /                  \
                  D = Hnode(A, B)        E = Hnode(C, C)
                  /            \          /             \
          A=Hnode(h0,h1)   B=Hnode(h2,h3)  C             C (duplicate)
           /      \         /      \      / \
          h0      h1       [h2]     h3    h4  h4 (duplicate)
          tx0     tx1       tx2      tx3   tx4

Proof path for tx2:
  level 0: h3 is RIGHT sibling of h2
  level 1: A  is LEFT  sibling of B
  level 2: E  is RIGHT sibling of D
```

Proof hashes (hex):
- h3 = `dd92b2355c6a1ab7cb2af661b69ab3b018a3899afef119404585041d56506b8b`
- A  = `e7f5de3cc43cc9ff4cbef41b922f3c341e2509204dfe188027df39185797ba6c`
- E  = `e25dbac69e9fa58e33d245d9012b00433c1f1f0074a59bf2ee100eaed821ec70`

Root = `0f71b647883ae08ea7b014002ba14a0b06ab201bccdae815e1d8b5c5850d0a3b`

Note: odd nodes are duplicated at EVERY level. For 5 leaves, h4 is duplicated into C, then C is duplicated into E. The proof for tx2 therefore contains **three** siblings, not two.
