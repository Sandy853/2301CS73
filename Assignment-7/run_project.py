#!/usr/bin/env python3
"""One command: compile, test/fuzz, deploy to local Anvil, interact, save deliverables.
Requires Foundry binaries: forge, anvil, cast. No pip dependencies.
"""
import json, os, shutil, subprocess, time, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "deliverables"
OUT.mkdir(exist_ok=True)
RPC = "http://127.0.0.1:8545"
# Anvil public development accounts ONLY. Never use these keys with real funds.
KEYS = [
 "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
 "0x59c6995e998f97a5a0044976f094538fcdaf5e6a6f15a3d4e6f67e4c4e7b3c", # replaced below using cast wallet derivation
]
MNEMONIC = "test test test test test test test test test test test junk"

def run(*cmd, check=True):
    r = subprocess.run([str(x) for x in cmd], cwd=ROOT, text=True, capture_output=True)
    if check and r.returncode: raise RuntimeError(f"{' '.join(map(str,cmd))}\n{r.stdout}\n{r.stderr}")
    return r.stdout.strip()

def rpc(method, params=None):
    data = json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params or []}).encode()
    req = urllib.request.Request(RPC, data, {"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=5) as resp: result=json.load(resp)
    if "error" in result: raise RuntimeError(result["error"])
    return result["result"]

def wallet(i):
    raw = run(
        "cast",
        "wallet",
        "derive",
        MNEMONIC,
        "--accounts",
        str(i + 1),
        "--insecure",
        "--json"
    )

    result = json.loads(raw)

    if not result.get("success", False):
        raise RuntimeError(
            f"Wallet derivation failed: {result.get('errors')}"
        )

    accounts = result.get("data", [])

    if len(accounts) <= i:
        raise ValueError(
            f"Expected account index {i}, "
            f"but only {len(accounts)} accounts were returned."
        )

    account = accounts[i]

    return account["address"], account["private_key"]

def receipt(txhash):
    for _ in range(80):
        r=rpc("eth_getTransactionReceipt",[txhash])
        if r: return r
        time.sleep(.15)
    raise TimeoutError(txhash)

def send(to,sig,key,*args,value=None):
    cmd=["cast","send",to,sig,*map(str,args),"--rpc-url",RPC,"--private-key",key,"--json"]
    if value is not None: cmd += ["--value",str(value)]
    d=json.loads(run(*cmd)); return receipt(d["transactionHash"])

def call(to,sig):
    return run("cast","call",to,sig,"--rpc-url",RPC)

def main():
    for exe in ("forge","anvil","cast"):
        if not shutil.which(exe): raise SystemExit(f"Missing {exe}. Install Foundry: https://getfoundry.sh/")
    print("[1/5] Compiling")
    build=run("forge","build"); (OUT/"build.log").write_text(build+"\n")
    print("[2/5] Running unit and fuzz tests")
    tests=run("forge","test","-vv"); (OUT/"test_results.txt").write_text(tests+"\n")
    gas=run("forge","test","--gas-report"); (OUT/"gas_report.txt").write_text(gas+"\n")
    print(tests[-2200:])
    node=subprocess.Popen(["anvil","--port","8545","--chain-id","31337","--mnemonic",MNEMONIC,"--silent"],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        for _ in range(50):
            if node.poll() is not None: raise RuntimeError("Anvil exited (is port 8545 in use?)")
            try: rpc("eth_chainId");break
            except Exception: time.sleep(.2)
        else: raise RuntimeError("Anvil not ready")
        buyer,bk=wallet(0);seller,sk=wallet(1);arbiter,ak=wallet(2)
        print("[3/5] Deploying and interacting with local Anvil")
        price=10**18
        # create uses Foundry artifact, not an external ABI file.
        dep=json.loads(run("forge","create","src/Escrow.sol:Escrow","--rpc-url",RPC,"--private-key",bk,"--broadcast","--json","--constructor-args",buyer,seller,arbiter,str(price)))
        addr=dep["deployedTo"]
        deployment=receipt(dep["transactionHash"])
        txs={"deployment":deployment}
        def step(name,sig,key,*args,value=None):
            txs[name]=send(addr,sig,key,*args,value=value)
            balance=int(rpc("eth_getBalance",[addr,"latest"]),16)
            liabilities=int(call(addr,"liabilities()(uint256)" ).split()[0])
            if balance != liabilities: raise AssertionError(f"Accounting failed after {name}: {balance} != {liabilities}")
            print(f"  {name}: balance={balance}, liabilities={liabilities}")
        step("fund","fund()",bk,value=price)
        step("dispute","dispute()",sk)
        step("resolve_to_seller","resolve(bool)",ak,"true")
        step("withdraw","withdraw()",sk)
        print("[4/5] Saving receipts, balances, events and bytecode")
        (OUT/"transaction_receipts.json").write_text(json.dumps(txs,indent=2)+"\n")
        code=rpc("eth_getCode",[addr,"latest"])
        (OUT/"deployed_bytecode.hex").write_text(code+"\n")
        summary={"chain_id":31337,"contract_address":addr,"buyer":buyer,"seller":seller,"arbiter":arbiter,
                 "price_wei":price,"final_state":int(call(addr,"state()(uint8)").split()[0]),
                 "final_contract_balance_wei":int(rpc("eth_getBalance",[addr,"latest"]),16),
                 "final_liabilities_wei":int(call(addr,"liabilities()(uint256)").split()[0]),
                 "bytecode_bytes":(len(code)-2)//2,
                 "gas_used":{k:int(v["gasUsed"],16) for k,v in txs.items()},
                 "event_topic_hashes":{k:[log["topics"][0] for log in v["logs"]] for k,v in txs.items()},
                 "receipt_statuses":{k:int(v["status"],16) for k,v in txs.items()}}
        assert all(x==1 for x in summary["receipt_statuses"].values())
        assert summary["final_state"]==6 and summary["final_liabilities_wei"]==0
        (OUT/"deployment_report.json").write_text(json.dumps(summary,indent=2)+"\n")
        print(json.dumps(summary,indent=2))
        print("[5/5] Completed: deliverables/ directory")
    finally:
        node.terminate()
        try: node.wait(timeout=3)
        except subprocess.TimeoutExpired: node.kill()

if __name__=="__main__": main()
