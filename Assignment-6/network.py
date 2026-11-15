"""Educational localhost TCP P2P blockchain demonstration. Not production consensus."""
import argparse
import asyncio
import hashlib
import json
import logging
import struct
import time
from collections import defaultdict, deque
from pathlib import Path

VERSION = 1
MAX_MESSAGE = 65536
TARGET = 2**248 - 1  # approximately 1/256 probability per hash
REWARD = 50
TTL = 120
KINDS = {'hello', 'peers', 'inv', 'get', 'tx', 'block', 'ping', 'error'}


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def merkle(txs):
    layer = [bytes.fromhex(digest(t)) for t in txs]
    if not layer:
        return hashlib.sha256(b'').hexdigest()
    while len(layer) > 1:
        if len(layer) % 2:
            layer.append(layer[-1])
        layer = [hashlib.sha256(layer[i] + layer[i+1]).digest() for i in range(0, len(layer), 2)]
    return layer[0].hex()


def txid(tx):
    return digest(tx)


def valid_tx(tx):
    return (isinstance(tx, dict) and set(tx) == {'sender', 'recipient', 'amount', 'fee', 'nonce', 'created'}
            and isinstance(tx['sender'], str) and 0 < len(tx['sender']) <= 40
            and isinstance(tx['recipient'], str) and 0 < len(tx['recipient']) <= 40
            and type(tx['amount']) is int and tx['amount'] > 0
            and type(tx['fee']) is int and tx['fee'] >= 0
            and type(tx['nonce']) is int and tx['nonce'] >= 0
            and type(tx['created']) is int and 0 < tx['created'] <= int(time.time()) + 60)


def genesis():
    header = {'version': VERSION, 'prev': '0'*64, 'merkle': merkle([]), 'timestamp': 0,
              'target': TARGET, 'nonce': 0}
    return {'header': header, 'txs': [], 'miner': 'genesis', 'coinbase': 0}

GENESIS = genesis()
GENESIS_ID = digest(GENESIS['header'])


def work(target):
    return (2**256) // (target + 1)


def apply_block(parent_state, block):
    state = {'balances': dict(parent_state['balances']), 'nonces': dict(parent_state['nonces'])}
    fees = 0
    for tx in block['txs']:
        if not valid_tx(tx):
            raise ValueError('invalid transaction')
        sender, recipient = tx['sender'], tx['recipient']
        if tx['nonce'] != state['nonces'].get(sender, 0):
            raise ValueError('nonce mismatch / conflict')
        cost = tx['amount'] + tx['fee']
        if state['balances'].get(sender, 0) < cost:
            raise ValueError('insufficient funds')
        state['balances'][sender] -= cost
        state['balances'][recipient] = state['balances'].get(recipient, 0) + tx['amount']
        state['nonces'][sender] = tx['nonce'] + 1
        fees += tx['fee']
    if type(block['coinbase']) is not int or block['coinbase'] != REWARD + fees:
        raise ValueError('bad coinbase')
    if not isinstance(block['miner'], str) or not 0 < len(block['miner']) <= 40:
        raise ValueError('bad miner')
    state['balances'][block['miner']] = state['balances'].get(block['miner'], 0) + block['coinbase']
    return state


class Node:
    def __init__(self, name, port, outdir, latency=0.03):
        self.name, self.port, self.latency = name, port, latency
        self.outdir = Path(outdir)
        self.outdir.mkdir(parents=True, exist_ok=True)
        self.logfile = self.outdir / f'{name}.jsonl'
        self.logfile.write_text('')
        self.server = None
        self.connections = {}  # peer -> writer
        self.known = {}  # peer -> port
        self.blocked = set()
        self.scores = defaultdict(int)
        self.rate = defaultdict(deque)
        self.blocks = {GENESIS_ID: GENESIS}
        self.states = {GENESIS_ID: {'balances': {'alice': 100, 'bob': 100, 'carol': 100}, 'nonces': {}}}
        self.heights = {GENESIS_ID: 0}
        self.works = {GENESIS_ID: 0}
        self.tip = GENESIS_ID
        self.mempool = {}
        self.seen = set()
        self.pending = set()
        self.lock = asyncio.Lock()
        self.tasks = set()

    def log(self, event, peer=None, obj=None, **details):
        item = {'timestamp': time.time(), 'node_id': self.name, 'peer_id': peer,
                'object_id': obj, 'event': event, **details}
        with self.logfile.open('a') as f:
            f.write(json.dumps(item, sort_keys=True) + '\n')
        if event in {'mined', 'reorg', 'partition', 'healed', 'reject', 'converged'}:
            print(f'[{self.name}] {event}: {details}', flush=True)

    async def start(self):
        self.server = await asyncio.start_server(self.handle, '127.0.0.1', self.port)
        self.log('start', port=self.port)

    async def stop(self):
        self.server.close()
        await self.server.wait_closed()
        for writer in list(self.connections.values()):
            writer.close()
        self.connections.clear()
        for task in list(self.tasks):
            task.cancel()

    async def send(self, peer, kind, **payload):
        if peer in self.blocked or peer not in self.connections:
            return
        msg = {'v': VERSION, 'type': kind, **payload}
        data = canonical(msg)
        if len(data) > MAX_MESSAGE:
            return
        await asyncio.sleep(self.latency)
        try:
            writer = self.connections[peer]
            writer.write(struct.pack('!I', len(data)) + data)
            await asyncio.wait_for(writer.drain(), 2)
        except (OSError, asyncio.TimeoutError, KeyError):
            self.connections.pop(peer, None)

    async def connect(self, peer, port):
        if peer == self.name or peer in self.blocked or peer in self.connections:
            return
        self.known[peer] = port
        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection('127.0.0.1', port), 1)
            self.connections[peer] = writer
            await self.send_raw(writer, {'v': VERSION, 'type': 'hello', 'node': self.name, 'port': self.port})
            self.spawn(self.handle_stream(reader, writer, expected=peer))
        except (OSError, asyncio.TimeoutError):
            self.log('connect_failed', peer=peer)

    def spawn(self, coro):
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def send_raw(self, writer, msg):
        data = canonical(msg)
        if len(data) > MAX_MESSAGE:
            raise ValueError('oversized outbound message')
        writer.write(struct.pack('!I', len(data)) + data)
        await asyncio.wait_for(writer.drain(), 2)

    async def handle(self, reader, writer):
        await self.handle_stream(reader, writer)

    async def handle_stream(self, reader, writer, expected=None):
        peer = expected
        try:
            while True:
                header = await asyncio.wait_for(reader.readexactly(4), 8)
                size = struct.unpack('!I', header)[0]
                if size == 0 or size > MAX_MESSAGE:
                    raise ValueError('invalid frame size')
                raw = await asyncio.wait_for(reader.readexactly(size), 8)
                msg = json.loads(raw)
                if not isinstance(msg, dict) or msg.get('v') != VERSION or msg.get('type') not in KINDS:
                    raise ValueError('bad protocol message')
                if peer is None:
                    if msg['type'] != 'hello' or not isinstance(msg.get('node'), str) or type(msg.get('port')) is not int:
                        raise ValueError('handshake required')
                    peer = msg['node']
                    if peer == self.name or peer in self.blocked or not 1024 <= msg['port'] <= 65535:
                        raise ValueError('invalid peer')
                    self.known[peer] = msg['port']
                    self.connections[peer] = writer
                    await self.send(peer, 'hello', node=self.name, port=self.port)
                    await self.send(peer, 'peers', peers=self.known)
                    await self.send(peer, 'inv', blocks=[self.tip], txs=list(self.mempool))
                    self.log('handshake', peer=peer)
                    continue
                if peer in self.blocked:
                    continue
                now = time.monotonic()
                q = self.rate[peer]
                while q and now - q[0] > 1:
                    q.popleft()
                q.append(now)
                if len(q) > 100:
                    self.scores[peer] -= 2
                    self.log('rate_limit', peer=peer)
                    if self.scores[peer] < -10:
                        break
                    continue
                await self.process(peer, msg)
        except (asyncio.IncompleteReadError, ConnectionError, OSError, asyncio.TimeoutError):
            pass
        except (ValueError, UnicodeError, json.JSONDecodeError, TypeError) as exc:
            self.scores[peer or 'unknown'] -= 3
            self.log('reject', peer=peer, reason=str(exc))
            try:
                await self.send_raw(writer, {'v': VERSION, 'type': 'error', 'reason': str(exc)[:100]})
            except (OSError, asyncio.TimeoutError):
                pass
        finally:
            if peer and self.connections.get(peer) is writer:
                self.connections.pop(peer, None)
            writer.close()

    async def process(self, peer, msg):
        kind = msg['type']
        if kind == 'hello':
            if msg.get('node') != peer:
                raise ValueError('peer identity changed')
            await self.send(peer, 'peers', peers=self.known)
            await self.send(peer, 'inv', blocks=[self.tip], txs=list(self.mempool))
        elif kind == 'peers':
            peers = msg.get('peers')
            if not isinstance(peers, dict) or len(peers) > 30:
                raise ValueError('invalid peers')
            for name, port in peers.items():
                if isinstance(name, str) and type(port) is int and 1024 <= port <= 65535 and name != self.name:
                    self.known[name] = port
        elif kind == 'inv':
            for field, object_type, store in [('blocks', 'block', self.blocks), ('txs', 'tx', self.mempool)]:
                ids = msg.get(field, [])
                if not isinstance(ids, list) or len(ids) > 100 or any(not isinstance(x, str) or len(x) != 64 for x in ids):
                    raise ValueError('invalid inventory')
                for oid in ids:
                    if oid not in store and (object_type, oid) not in self.pending:
                        self.pending.add((object_type, oid))
                        await self.send(peer, 'get', object_type=object_type, object_id=oid)
                        self.log('request', peer, oid, kind=object_type)
        elif kind == 'get':
            objtype, oid = msg.get('object_type'), msg.get('object_id')
            if objtype not in {'tx', 'block'} or not isinstance(oid, str):
                raise ValueError('invalid get')
            store = self.blocks if objtype == 'block' else self.mempool
            if oid in store:
                await self.send(peer, objtype, data=store[oid])
        elif kind == 'tx':
            tx = msg.get('data')
            if not isinstance(tx, dict):
                raise ValueError('invalid tx payload')
            oid = txid(tx)
            self.pending.discard(('tx', oid))
            if await self.add_tx(tx):
                self.log('tx_accepted', peer, oid)
                await self.broadcast_inv(txs=[oid], exclude=peer)
        elif kind == 'block':
            block = msg.get('data')
            if not isinstance(block, dict) or not isinstance(block.get('header'), dict):
                raise ValueError('invalid block payload')
            oid = digest(block['header'])
            self.pending.discard(('block', oid))
            accepted = await self.add_block(block, peer)
            if accepted:
                await self.broadcast_inv(blocks=[oid], exclude=peer)
            elif block['header'].get('prev') not in self.blocks:
                await self.send(peer, 'get', object_type='block', object_id=block['header']['prev'])
        elif kind == 'ping':
            self.log('ping', peer)
        elif kind == 'error':
            self.log('peer_error', peer, reason=str(msg.get('reason', ''))[:100])

    async def broadcast_inv(self, blocks=None, txs=None, exclude=None):
        for peer in list(self.connections):
            if peer != exclude and peer not in self.blocked:
                await self.send(peer, 'inv', blocks=blocks or [], txs=txs or [])

    async def add_tx(self, tx):
        if not valid_tx(tx):
            return False
        oid = txid(tx)
        if oid in self.mempool or oid in self.seen:
            return False
        if int(time.time()) - tx['created'] > TTL:
            return False
        state = self.states[self.tip]
        if tx['nonce'] != state['nonces'].get(tx['sender'], 0):
            return False
        if state['balances'].get(tx['sender'], 0) < tx['amount'] + tx['fee']:
            return False
        for other in list(self.mempool.values()):
            if other['sender'] == tx['sender'] and other['nonce'] == tx['nonce']:
                if tx['fee'] <= other['fee']:
                    return False
                self.mempool.pop(txid(other), None)
        self.mempool[oid] = tx
        self.seen.add(oid)
        return True

    def path(self, tip):
        chain = []
        while tip != GENESIS_ID:
            chain.append(tip)
            tip = self.blocks[tip]['header']['prev']
        return list(reversed(chain))

    async def add_block(self, block, peer=None):
        try:
            header = block['header']
            if set(header) != {'version', 'prev', 'merkle', 'timestamp', 'target', 'nonce'}:
                raise ValueError('bad header fields')
            if header['version'] != VERSION or type(header['target']) is not int or header['target'] != TARGET:
                raise ValueError('wrong version/target')
            if type(header['nonce']) is not int or header['nonce'] < 0 or type(header['timestamp']) is not int:
                raise ValueError('invalid nonce/time')
            if header['timestamp'] > int(time.time()) + 60:
                raise ValueError('future block')
            if not isinstance(header['prev'], str) or len(header['prev']) != 64:
                raise ValueError('invalid parent hash')
            if not isinstance(block.get('txs'), list) or len(block['txs']) > 100:
                raise ValueError('invalid tx list')
            if header['merkle'] != merkle(block['txs']):
                raise ValueError('bad merkle root')
            oid = digest(header)
            if int(oid, 16) > TARGET:
                raise ValueError('invalid proof of work')
            if oid in self.blocks:
                return False
            parent = header['prev']
            if parent not in self.blocks:
                self.log('orphan', peer, oid, parent=parent)
                return False
            if header['timestamp'] < self.blocks[parent]['header']['timestamp']:
                raise ValueError('timestamp regression')
            state = apply_block(self.states[parent], block)
        except (ValueError, KeyError, TypeError, OverflowError) as exc:
            self.scores[peer or 'local'] -= 2
            self.log('reject', peer, reason=str(exc))
            return False
        self.blocks[oid] = block
        self.states[oid] = state
        self.heights[oid] = self.heights[parent] + 1
        self.works[oid] = self.works[parent] + work(TARGET)
        self.log('block_accepted', peer, oid, height=self.heights[oid], cumulative_work=self.works[oid])
        if (self.works[oid], oid) > (self.works[self.tip], self.tip):
            old = self.tip
            old_path, new_path = self.path(old), self.path(oid)
            self.tip = oid
            new_ids = {txid(tx) for bid in new_path for tx in self.blocks[bid]['txs']}
            candidates = list(self.mempool.values())
            for bid in old_path:
                if bid not in new_path:
                    candidates.extend(self.blocks[bid]['txs'])
            self.mempool.clear()
            self.seen.difference_update(txid(t) for t in candidates)
            for tx in sorted(candidates, key=lambda t: (-t['fee'], txid(t))):
                if txid(tx) not in new_ids:
                    await self.add_tx(tx)
            if old != GENESIS_ID and old not in new_path:
                self.log('reorg', peer, oid, old_tip=old, new_tip=oid,
                         restored_txs=len([t for t in candidates if txid(t) in self.mempool]))
            self.log('tip', peer, oid, height=self.heights[oid])
        return True

    async def mine(self, txs=None):
        txs = txs if txs is not None else sorted(self.mempool.values(), key=lambda t: (-t['fee'], txid(t)))
        parent = self.tip
        fees = sum(tx['fee'] for tx in txs)
        header = {'version': VERSION, 'prev': parent, 'merkle': merkle(txs),
                  'timestamp': int(time.time()), 'target': TARGET, 'nonce': 0}
        while int(digest(header), 16) > TARGET:
            header['nonce'] += 1
        block = {'header': header, 'txs': txs, 'miner': self.name, 'coinbase': REWARD + fees}
        if not await self.add_block(block):
            raise RuntimeError('locally mined invalid block')
        self.log('mined', obj=digest(header), height=self.heights[self.tip], tx_count=len(txs))
        await self.broadcast_inv(blocks=[digest(header)])
        return digest(header)

    def summary(self):
        return {'node_id': self.name, 'tip': self.tip, 'height': self.heights[self.tip],
                'cumulative_work': self.works[self.tip], 'mempool': list(self.mempool),
                'balances': self.states[self.tip]['balances'], 'peers': list(self.connections),
                'peer_scores': dict(self.scores)}


async def wait_until(predicate, seconds=6):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.05)
    return False


async def experiment(args):
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    nodes = [Node(f'N{i}', args.base_port + i, out, args.latency) for i in range(5)]
    try:
        for n in nodes:
            await n.start()
        # Connect full mesh. Handshake exchanges peer inventories.
        for i in range(5):
            for j in range(i+1, 5):
                await nodes[i].connect(nodes[j].name, nodes[j].port)
        await asyncio.sleep(0.5)
        # Each side has internal connectivity, cross-partition messages are dropped.
        for n in nodes[:2]:
            n.blocked.update(x.name for x in nodes[2:])
            n.log('partition', group='A')
        for n in nodes[2:]:
            n.blocked.update(x.name for x in nodes[:2])
            n.log('partition', group='B')
        # Two valid independent transactions, each initially confined to a partition.
        now = int(time.time())
        stale_tx = {'sender': 'alice', 'recipient': 'bob', 'amount': 7, 'fee': 2, 'nonce': 0, 'created': now}
        winning_tx = {'sender': 'carol', 'recipient': 'bob', 'amount': 4, 'fee': 3, 'nonce': 0, 'created': now}
        assert await nodes[0].add_tx(stale_tx)
        await nodes[0].broadcast_inv(txs=[txid(stale_tx)])
        assert await nodes[2].add_tx(winning_tx)
        await nodes[2].broadcast_inv(txs=[txid(winning_tx)])
        await wait_until(lambda: txid(stale_tx) in nodes[1].mempool and
                         txid(winning_tx) in nodes[3].mempool)
        await nodes[0].mine([stale_tx])
        await nodes[2].mine([winning_tx])
        await wait_until(lambda: nodes[1].tip == nodes[0].tip and nodes[3].tip == nodes[2].tip)
        await nodes[3].mine([])  # group B has strictly more cumulative work
        await wait_until(lambda: nodes[2].tip == nodes[3].tip)
        for n in nodes:
            n.blocked.clear()
            n.log('healed')
        # Announce winning tip. Missing parent is requested on receipt of child.
        await nodes[3].broadcast_inv(blocks=[nodes[3].tip])
        await asyncio.sleep(0.3)
        # Reannounce all branch blocks so inventory-based synchronization can fill parents.
        for _ in range(5):
            for n in nodes:
                await n.broadcast_inv(blocks=n.path(n.tip))
            if await wait_until(lambda: len({n.tip for n in nodes}) == 1, 2):
                break
        # Reannounce transactions resurrected from stale blocks after reorganisation.
        for n in nodes[:2]:
            await n.broadcast_inv(txs=list(n.mempool))
        await wait_until(lambda: all(txid(stale_tx) in n.mempool for n in nodes), 5)
        converged = len({n.tip for n in nodes}) == 1
        restored = all(txid(stale_tx) in n.mempool for n in nodes)
        for n in nodes:
            n.log('converged' if converged else 'not_converged',
                  tip=n.tip, restored_stale_tx=txid(stale_tx) in n.mempool)
        report = {'experiment': 'five-node partition/reorg', 'converged': converged,
                  'stale_transaction_restored_on_all_nodes': restored,
                  'stale_transaction_id': txid(stale_tx), 'winning_transaction_id': txid(winning_tx),
                  'nodes': [n.summary() for n in nodes]}
        (out / 'report.json').write_text(json.dumps(report, indent=2))
        (out / 'summary.txt').write_text(
            'P2P MEMPOOL AND BLOCK RELAY EXPERIMENT\n'
            f'Converged: {converged}\nStale transaction reconsidered: {restored}\n'
            + '\n'.join(f"{n.name}: height={n.heights[n.tip]} work={n.works[n.tip]} tip={n.tip[:16]} mempool={len(n.mempool)}" for n in nodes) + '\n')
        print((out / 'summary.txt').read_text())
        if not converged or not restored:
            raise RuntimeError('experiment assertions failed; inspect JSONL logs')
    finally:
        for n in nodes:
            if n.server:
                await n.stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='deliverables')
    parser.add_argument('--base-port', type=int, default=19000)
    parser.add_argument('--latency', type=float, default=0.02)
    args = parser.parse_args()
    asyncio.run(experiment(args))


if __name__ == '__main__':
    main()
