import unittest
from blockchain import *

class ChainTests(unittest.TestCase):
    def setUp(self):
        self.alice, pk = keypair(); self.a = address(pk)
        self.bob, pk = keypair(); self.b = address(pk)
        self.target = MAX_HASH >> 4
        self.node = Node()
        self.gen, _ = mine(ZERO, [coinbase(self.a, 50, 0, 'gen')], self.target)
        self.node.add(self.gen)
    def next(self, txs=None, target=None, parent=None, height=1, tag='next', reward=50):
        p = parent or self.gen.hash()
        return mine(p, [coinbase(self.a, reward, height, tag)] + (txs or []), target or self.target)[0]
    def spend(self, value=40, change=9):
        return make_spend([{'txid':txid(self.gen.transactions[0]), 'index':0}], [output(value,self.b),output(change,self.a)], [self.alice])
    def reject(self, block, message):
        old = snapshot(self.node); count = len(self.node.records)
        with self.assertRaisesRegex(ValidationError, message): self.node.add(block)
        self.assertEqual(snapshot(self.node), old); self.assertEqual(len(self.node.records), count)
    def test_genesis(self): self.assertEqual(len(self.node.utxos()), 1)
    def test_header_length(self): self.assertEqual(len(self.gen.header.encode()), 116)
    def test_pow(self): self.assertLessEqual(int(self.gen.hash(),16),self.target)
    def test_merkle_determinism(self): self.assertEqual(merkle(self.gen.transactions),merkle(self.gen.transactions))
    def test_merkle_changes(self): self.assertNotEqual(merkle([coinbase(self.a,50,0,'x')]),merkle([coinbase(self.a,50,0,'y')]))
    def test_work_inverse_target(self): self.assertGreater(work(MAX_HASH>>8),work(MAX_HASH>>4))
    def test_valid_spend(self): self.assertTrue(self.node.add(self.next([self.spend()], reward=51))['active'])
    def test_invalid_merkle(self):
        b=self.next(); b.header.merkle_root=ZERO; self.reject(b,'Merkle')
    def test_invalid_pow(self):
        b=self.next(); b.header.nonce=next(i for i in range(10000) if int(Header(1,b.header.previous,b.header.merkle_root,b.header.timestamp,b.header.target,i).hash(),16)>self.target); self.reject(b,'proof of work')
    def test_excess_coinbase(self): self.reject(self.next(reward=51),'excess coinbase')
    def test_excess_outputs(self): self.reject(self.next([self.spend(50,1)]),'outputs exceed inputs')
    def test_missing_input(self):
        tx=make_spend([{'txid':'ff'*32,'index':0}],[output(1,self.b)],[self.alice]); self.reject(self.next([tx]),'missing or already spent')
    def test_bad_signature(self):
        tx=self.spend(); tx['witnesses'][0]['signature']='00'*64; self.reject(self.next([tx]),'invalid signature')
    def test_wrong_owner(self):
        tx=make_spend([{'txid':txid(self.gen.transactions[0]),'index':0}],[output(40,self.b)],[self.bob]); self.reject(self.next([tx]),'wrong public key')
    def test_duplicate_input(self):
        i={'txid':txid(self.gen.transactions[0]),'index':0}; tx=make_spend([i,i],[output(20,self.b)],[self.alice,self.alice]); self.reject(self.next([tx]),'duplicate input')
    def test_negative_output(self):
        tx=self.spend(); tx['outputs'][0]['value']=-1; self.reject(self.next([tx]),'invalid transaction output')
    def test_overflow_output(self):
        tx=self.spend(); tx['outputs'][0]['value']=MAX_MONEY+1; self.reject(self.next([tx]),'invalid transaction output')
    def test_missing_coinbase(self):
        b=self.next(); b.transactions=[]; self.reject(b,'Merkle')
    def test_multiple_coinbase(self):
        b=self.next([coinbase(self.a,50,1,'extra')]); self.reject(b,'multiple coinbase')
    def test_wrong_height(self): self.reject(self.next(height=2),'coinbase height')
    def test_wrong_version(self):
        b=self.next(); b.header.version=2; self.reject(b,'version')
    def test_unknown_parent(self):
        b,_=mine('aa'*32,[coinbase(self.a,50,1)],self.target); self.reject(b,'unknown parent')
    def test_duplicate_block(self): self.reject(self.gen,'duplicate block')
    def test_bad_target_limit(self):
        n=Node(max_target=MAX_HASH>>6); self.assertRaisesRegex(ValidationError,'target',n.add,self.gen)
    def test_second_genesis(self):
        b,_=mine(ZERO,[coinbase(self.a,50,0,'other')],self.target); self.reject(b,'second genesis')
    def test_longer_lower_work_loses(self):
        low1=self.next(tag='low1'); self.node.add(low1)
        low2=self.next(parent=low1.hash(),height=2,tag='low2'); self.node.add(low2)
        high=self.next(target=MAX_HASH>>8,tag='high'); self.node.add(high)
        self.assertEqual(self.node.tip,high.hash())
        self.assertEqual(self.node.records[high.hash()].height,1)
    def test_reorg_restores_outputs(self):
        old=self.next([self.spend()],reward=51,tag='old'); self.node.add(old)
        self.assertIn(f'{txid(self.spend())}:0',self.node.utxos())
        high=self.next(target=MAX_HASH>>8,tag='high'); self.node.add(high)
        self.assertIn(f'{txid(self.gen.transactions[0])}:0',self.node.utxos())
        self.assertNotIn(f'{txid(self.spend())}:0',self.node.utxos())
    def test_double_spend_same_branch(self):
        t=self.spend(); b=self.next([t],reward=51); self.node.add(b)
        nextb=self.next([t],parent=b.hash(),height=2,tag='second'); self.reject(nextb,'missing or already spent')
    def test_wrong_fee_reward(self): self.reject(self.next([self.spend()],reward=52),'excess coinbase')
    def test_valid_fee_reward(self): self.node.add(self.next([self.spend()],reward=51))
    def test_state_copy(self):
        copy=self.node.utxos(); copy.clear(); self.assertTrue(self.node.utxos())
    def test_merkle_odd(self): self.assertEqual(len(merkle([coinbase(self.a,50,0),coinbase(self.a,50,1),coinbase(self.a,50,2)])),64)
    def test_header_roundtrip_deterministic(self): self.assertEqual(self.gen.header.encode(),self.gen.header.encode())
    def test_invalid_empty_inputs(self):
        tx={'kind':'spend','inputs':[],'outputs':[output(1,self.b)],'witnesses':[]}; self.reject(self.next([tx]),'no inputs')
    def test_invalid_timestamp(self):
        b=self.next(); b.header.timestamp=-1; self.reject(b,'timestamp')
    def test_invalid_kind(self):
        tx={'kind':'unknown'}; self.reject(self.next([tx]),'unexpected transaction kind')

if __name__=='__main__': unittest.main()
