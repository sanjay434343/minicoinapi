from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import json, os, time, hashlib, math
from typing import List

app = FastAPI(title="MiniCoin API", description="Bitcoin-like crypto API in Python", version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with frontend domain if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CHAIN_FILE = "blockchain.json"
USER_FILE = "users.json"

# ------------------ Blockchain Classes ------------------

class Block:
    def __init__(self, index, timestamp, transactions, previous_hash):
        self.index = index
        self.timestamp = timestamp
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        tx_str = json.dumps(self.transactions, sort_keys=True)
        raw = f"{self.index}{self.timestamp}{tx_str}{self.previous_hash}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def to_dict(self):
        return {
            'index': self.index,
            'timestamp': self.timestamp,
            'transactions': self.transactions,
            'previous_hash': self.previous_hash,
            'hash': self.hash
        }

# ------------------ File Helpers ------------------

def load_json(file):
    return json.load(open(file)) if os.path.exists(file) else []

def save_json(file, data):
    json.dump(data, open(file, 'w'), indent=2)

def get_chain():
    return load_json(CHAIN_FILE)

def save_chain(chain):
    save_json(CHAIN_FILE, chain)

def get_users():
    return load_json(USER_FILE)

def save_users(users):
    save_json(USER_FILE, users)

def find_user(username):
    return next((u for u in get_users() if u['username'] == username), None)

# ------------------ Core Logic ------------------

def create_block():
    chain = get_chain()
    users = get_users()
    total_coins = sum(u['balance'] for u in users)
    expected_blocks = math.floor(total_coins / 1000)

    if len(chain) < expected_blocks:
        new_block = Block(
            index=len(chain),
            timestamp=time.time(),
            transactions=[{"info": "Auto block for 1000 coin milestone"}],
            previous_hash=chain[-1]['hash'] if chain else '0'
        )
        chain.append(new_block.to_dict())
        save_chain(chain)

def get_balance(address):
    chain = get_chain()
    balance = 0
    for block in chain:
        for tx in block.get("transactions", []):
            if tx.get("to") == address:
                balance += tx["amount"]
            if tx.get("from") == address:
                balance -= tx["amount"]
    return balance

# ------------------ Routes ------------------

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <h1>🚀 MiniCoin API</h1>
    <ul>
      <li>POST /join { username }</li>
      <li>POST /buy { username, amount }</li>
      <li>POST /send { from_user, to, amount }</li>
      <li>GET /wallet/{username}</li>
      <li>GET /chain</li>
    </ul>
    """

@app.post("/join")
async def join_user(data: dict):
    users = get_users()
    if find_user(data['username']):
        return {"message": "User already exists"}
    addr = hashlib.sha256(data['username'].encode()).hexdigest()
    users.append({"username": data['username'], "address": addr, "balance": 0})
    save_users(users)
    return {"message": "User joined", "address": addr}

@app.post("/buy")
async def buy_coin(data: dict):
    users = get_users()
    user = find_user(data['username'])
    if not user:
        return {"error": "User not found"}

    amount = int(data.get('amount', 0))
    if amount <= 0:
        return {"error": "Invalid amount"}

    # Record transaction in a block
    chain = get_chain()
    tx = {
        "from": "system",
        "to": user['address'],
        "amount": amount
    }
    new_block = Block(
        index=len(chain),
        timestamp=time.time(),
        transactions=[tx],
        previous_hash=chain[-1]['hash'] if chain else '0'
    )
    chain.append(new_block.to_dict())
    save_chain(chain)

    create_block()

    return {"message": "Coins purchased", "address": user['address'], "amount": amount}

@app.post("/send")
async def send_coin(data: dict):
    users = get_users()
    sender = find_user(data['from_user'])
    if not sender:
        return {"error": "Sender not found"}

    amount = int(data.get('amount', 0))
    if amount <= 0:
        return {"error": "Invalid amount"}

    sender_balance = get_balance(sender['address'])
    if sender_balance < amount:
        return {"error": "Insufficient balance"}

    receiver = next((u for u in users if u['username'] == data['to'] or u['address'] == data['to']), None)
    if not receiver:
        addr = hashlib.sha256(data['to'].encode()).hexdigest()
        receiver = {"username": data['to'], "address": addr, "balance": 0}
        users.append(receiver)

    save_users(users)

    # Record transaction in block
    chain = get_chain()
    tx = {
        "from": sender['address'],
        "to": receiver['address'],
        "amount": amount
    }
    new_block = Block(
        index=len(chain),
        timestamp=time.time(),
        transactions=[tx],
        previous_hash=chain[-1]['hash'] if chain else '0'
    )
    chain.append(new_block.to_dict())
    save_chain(chain)
    create_block()

    return {"message": "Transaction successful", "from": sender['address'], "to": receiver['address'], "amount": amount}

@app.get("/wallet/{username}")
async def get_wallet(username: str):
    user = find_user(username)
    if not user:
        return {"error": "User not found"}
    balance = get_balance(user['address'])
    return {"username": username, "address": user['address'], "balance": balance}

@app.get("/chain")
async def full_chain():
    return get_chain()
