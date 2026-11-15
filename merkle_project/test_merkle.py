import copy
import json
import unittest
from merkle import EMPTY_ROOT, leaf_hash, node_hash, root, prove, verify


class MerkleTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(root([]), EMPTY_ROOT.hex())

    def test_single(self):
        self.assertEqual(root([b'a']), leaf_hash(b'a').hex())
        self.assertTrue(verify(b'a', prove([b'a'], 0), root([b'a'])))

    def test_even_odd_and_large(self):
        for size in (2, 3, 5, 8, 1024):
            leaves = [f'tx{i}'.encode() for i in range(size)]
            expected = root(leaves)
            for i in sorted({0, size // 2, size - 1}):
                proof = prove(leaves, i)
                self.assertTrue(verify(leaves[i], proof, expected))
                try:
                    self.assertFalse(verify(b'wrong', proof, expected))
                except ValueError:
                    # A changed leaf breaks the required self-duplicate at an odd level.
                    pass
                self.assertEqual(json.loads(json.dumps(proof)), proof)

    def test_bad_proofs(self):
        leaves = [f'tx{i}'.encode() for i in range(5)]
        good = prove(leaves, 4)
        variants = []
        for change in ('index', 'direction', 'hash', 'extra', 'short', 'duplicate', 'field'):
            p = copy.deepcopy(good)
            if change == 'index': p['leaf_index'] = 5
            if change == 'direction': p['siblings'][0]['side'] = 'left'
            if change == 'hash': p['siblings'][0]['hash'] = 'gg' * 32
            if change == 'extra': p['siblings'].append(p['siblings'][0])
            if change == 'short': p['siblings'].pop()
            if change == 'duplicate': p['siblings'][0]['hash'] = '00' * 32
            if change == 'field': p['unexpected'] = 1
            variants.append(p)
        for p in variants:
            with self.subTest(p=p), self.assertRaises(ValueError):
                verify(leaves[4], p, root(leaves))

    def test_domain_separation(self):
        self.assertNotEqual(leaf_hash(b'abc'), node_hash(b'\x00'*32, b'\x00'*32))


if __name__ == '__main__':
    unittest.main()
