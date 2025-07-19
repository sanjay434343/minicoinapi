from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import json, os, time, hashlib

app = FastAPI(title="MiniCoin API", description="Bitcoin-like crypto API in Python", version="1.0.0")

# CORS setup to allow frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Use your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CHAIN_FILE = "blockchain.json"
USER_FILE = "users.json"

# Blockchain block class
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

# JSON helpers
def load_json(file):
    return json.load(open(file)) if os.path.exists(file) else []

def save_json(file, data):
    json.dump(data, open(file, 'w'), indent=2)

# Load blockchain & users
def get_chain():
    return load_json(CHAIN_FILE)

def get_users():
    return load_json(USER_FILE)

def save_chain(chain):
    save_json(CHAIN_FILE, chain)

def save_users(users):
    save_json(USER_FILE, users)

def find_user(username):
    return next((u for u in get_users() if u['username'] == username), None)

# Auto-block creation every 1000 coins
def create_block():
    chain = get_chain()
    users = get_users()
    total_coins = sum(u['balance'] for u in users)
    if total_coins >= 1000 * (len(chain) + 1):
        new_block = Block(
            index=len(chain),
            timestamp=time.time(),
            transactions=[{"info": "Milestone block"}],
            previous_hash=chain[-1]['hash'] if chain else '0'
        )
        chain.append(new_block.to_dict())
        save_chain(chain)

# -------------------- ROUTES ----------------------

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <h1>🚀 MiniCoin API</h1>
    <ul>
      <li><b>POST</b> /join <code>{ "username": "alice" }</code></li>
      <li><b>POST</b> /buy <code>{ "username": "alice", "amount": 100 }</code></li>
      <li><b>POST</b> /send <code>{ "from_user": "alice", "to": "bob", "amount": 10 }</code></li>
      <li><b>GET</b> /wallet/{username}</li>
      <li><b>GET</b> /chain</li>
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
    user['balance'] += data['amount']
    save_users(users)
    create_block()
    return {"message": "Coins purchased", "new_balance": user['balance']}

@app.post("/send")
async def send_coin(data: dict):
    users = get_users()
    sender = find_user(data['from_user'])
    if not sender or sender['balance'] < data['amount']:
        return {"error": "Invalid sender or insufficient funds"}

    receiver = next((u for u in users if u['username'] == data['to'] or u['address'] == data['to']), None)
    if not receiver:
        addr = hashlib.sha256(data['to'].encode()).hexdigest()
        receiver = {"username": data['to'], "address": addr, "balance": 0}
        users.append(receiver)

    sender['balance'] -= data['amount']
    receiver['balance'] += data['amount']
    save_users(users)

    chain = get_chain()
    new_block = Block(
        index=len(chain),
        timestamp=time.time(),
        transactions=[{
            "from": sender['username'],
            "to": receiver['username'],
            "amount": data['amount']
        }],
        previous_hash=chain[-1]['hash'] if chain else '0'
    )
    chain.append(new_block.to_dict())
    save_chain(chain)
    return {"message": "Transaction successful"}

@app.get("/wallet/{username}")
async def get_wallet(username: str):
    user = find_user(username)
    if not user:
        return {"error": "User not found"}
    return user

@app.get("/chain")
async def full_chain():
    return get_chain()
