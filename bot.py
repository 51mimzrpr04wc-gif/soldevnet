import requests
import time
import re
import os
from queue import Queue, Empty
from threading import Thread, Lock
from flask import Flask
from solana.rpc.api import Client
from solders.keypair import Keypair 
from solders.transaction import Transaction
from solders.system_program import transfer, TransferParams
from solders.pubkey import Pubkey
from solders.message import Message

# ================= KONFIGURASI =================
DEST_WALLET = "2vxYoyZMnsx4T2oVNSbM3HgtRzu6QGXKNYfuWDJX2dQ1"
SOLANA_RPC = "https://api.devnet.solana.com/"
MAX_THREADS = 100
# ===============================================

app = Flask(__name__)
proxy_queue = Queue()
direct_client = Client(SOLANA_RPC)
print_lock = Lock()
stats = {"success": 0, "attempt": 0}

@app.route('/')
def health_check():
    return f"BOT STATUS: RUNNING | SUCCESS: {stats['success']} | MAIN BAL: {get_main_balance()} SOL"

def get_main_balance():
    try:
        pubkey = Pubkey.from_string(DEST_WALLET)
        balance = direct_client.get_balance(pubkey)
        return balance.value / 1000000000
    except: return "N/A"

def fetch_proxies():
    sources = [
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
        "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
        "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/proxies.txt",
        "https://raw.githubusercontent.com/roostercoinlo/Free-Proxy/main/http.txt",
        "https://raw.githubusercontent.com/opsxcq/proxy-list/master/list.txt",
        "https://alexa.lr2b.com/proxylab.txt"
    ]
    all_found = []
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"[*] REFRESHING PROXIES... | SALDO UTAMA: {get_main_balance()} SOL")
    
    for s in sources:
        try:
            r = requests.get(s, timeout=5)
            found = re.findall(r'\d+\.\d+\.\d+\.\d+:\d+', r.text)
            all_found.extend(found)
        except: continue
    
    unique = list(set([p.strip() for p in all_found]))
    for p in unique:
        proxy_queue.put(p)
    return len(unique)

def worker(worker_id):
    while True:
        try:
            proxy = proxy_queue.get(timeout=5)
            proxies_config = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
            new_wallet = Keypair()
            new_pubkey = new_wallet.pubkey()
            
            payload = {"jsonrpc": "2.0", "id": 1, "method": "requestAirdrop", "params": [str(new_pubkey), 1000000000]}
            
            try:
                resp = requests.post(SOLANA_RPC, json=payload, proxies=proxies_config, timeout=8)
                if resp.status_code == 200 and "result" in resp.json():
                    with print_lock:
                        stats["attempt"] += 1
                        print(f"\r[+] AIRDROP: {stats['attempt']} | Cek saldo di thread {worker_id}...", end="", flush=True)

                    # Loop mandiri per thread (tidak saling tunggu)
                    for _ in range(15): 
                        time.sleep(2.5)
                        try:
                            bal = direct_client.get_balance(new_pubkey).value
                            if bal >= 1000000000:
                                bh = direct_client.get_latest_blockhash().value.blockhash
                                ix = transfer(TransferParams(
                                    from_pubkey=new_pubkey, 
                                    to_pubkey=Pubkey.from_string(DEST_WALLET), 
                                    lamports=bal - 5000
                                ))
                                
                                # Format sesuai Solders 0.21.0
                                msg = Message([ix], new_pubkey)
                                txn = Transaction([new_wallet], msg, bh)
                                
                                direct_client.send_transaction(txn)
                                with print_lock:
                                    stats["success"] += 1
                                    print(f"\n[✅] SUCCESS! TOTAL MASUK: {stats['success']} SOL")
                                break
                        except: continue
            except: pass
            proxy_queue.task_done()
        except Empty: break

def run_bot():
    while True:
        count = fetch_proxies()
        print(f"[*] Proxy Loaded: {count} | Threads: {MAX_THREADS}")
        threads = []
        for i in range(MAX_THREADS):
            t = Thread(target=worker, args=(i,))
            t.daemon = True
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
        time.sleep(5)

if __name__ == "__main__":
    # Jalankan bot di background
    Thread(target=run_bot, daemon=True).start()
    # Flask untuk Railway binding port
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
