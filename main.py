from fastapi import FastAPI, Request
from pydantic import BaseModel
import json, os, time, hashlib, math
from typing import List, Dict

CHAIN_FILE = "blockchain.json"
USER_FILE = "users.json"
app = FastAPI()

# ----------------- Core Classes ------------------

class Block:
    def __init__(self, index, prev_hash, timestamp, data):
        self.index = index
        self.prev_hash = prev_hash
        self.timestamp = timestamp
        self.data = data
        self.hash = self.compute_hash()

    def compute_hash(self):
        block_string = f"{self.index}{self.prev_hash}{self.timestamp}{self.data}"
        return hashlib.sha256(block_string.encode()).hexdigest()

    def to_dict(self):
        return {
            "index": self.index,
            "prev_hash": self.prev_hash,
            "timestamp": self.timestamp,
            "data": self.data,
            "hash": self.hash
        }

class Blockchain:
    def __init__(self):
        self.chain: List[Block] = []
        self.load_chain()

    def create_genesis_block(self):
        genesis_block = Block(0, "0", time.time(), [])
        self.chain.append(genesis_block)
        self.save_chain()

    def add_block(self, data):
        prev_block = self.chain[-1]
        new_block = Block(len(self.chain), prev_block.hash, time.time(), data)
        self.chain.append(new_block)
        self.save_chain()

    def save_chain(self):
        with open(CHAIN_FILE, "w") as f:
            json.dump([b.to_dict() for b in self.chain], f, indent=2)

    def load_chain(self):
        if os.path.exists(CHAIN_FILE):
            try:
                with open(CHAIN_FILE, "r") as f:
                    data = json.load(f)
                    self.chain = [
                        Block(d["index"], d["prev_hash"], d["timestamp"], d["data"])
                        for d in data
                    ]
            except:
                os.remove(CHAIN_FILE)
                self.create_genesis_block()
        else:
            self.create_genesis_block()

    def auto_block_if_needed(self):
        users = load_users()
        total = sum(user["coins"] for user in users.values())
        expected = math.floor(total / 1000)
        while len(self.chain) - 1 < expected:
            self.add_block([])

# ----------------- User Functions ------------------

def load_users():
    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USER_FILE, "w") as f:
        json.dump(users, f, indent=2)

def get_or_create_user(username):
    users = load_users()
    if username not in users:
        users[username] = {
            "address": hashlib.sha256(f"{username}{time.time()}".encode()).hexdigest()[:16],
            "coins": 0
        }
        save_users(users)
    return users[username]

def resolve_user_by_address(address):
    users = load_users()
    for name, data in users.items():
        if data["address"] == address:
            return name
    return None

# ----------------- API Schema ------------------

class JoinRequest(BaseModel):
    username: str

class BuyRequest(BaseModel):
    username: str
    amount: int

class SendRequest(BaseModel):
    from_user: str
    to: str
    amount: int

# ----------------- API Routes ------------------

bc = Blockchain()

@app.post("/join")
def join_user(req: JoinRequest):
    user = get_or_create_user(req.username)
    return {"message": "User joined", "user": user}

@app.get("/wallet/{username}")
def get_wallet(username: str):
    users = load_users()
    if username in users:
        return users[username]
    return {"error": "User not found"}

@app.post("/buy")
def buy_coins(req: BuyRequest):
    user = get_or_create_user(req.username)
    users = load_users()
    users[req.username]["coins"] += req.amount
    tx = {"user": req.username, "type": "buy", "amount": req.amount, "time": time.time()}
    bc.chain[-1].data.append(tx)
    save_users(users)
    bc.auto_block_if_needed()
    bc.save_chain()
    return {"message": f"{req.amount} coins bought", "user": users[req.username]}

@app.post("/send")
def send_coins(req: SendRequest):
    users = load_users()
    sender = get_or_create_user(req.from_user)

    if sender["coins"] < req.amount:
        return {"error": "Insufficient balance"}

    receiver_name = req.to if req.to in users else resolve_user_by_address(req.to)

    if not receiver_name:
        receiver_name = f"user_{req.to[:6]}"
        users[receiver_name] = {"address": req.to, "coins": 0}
        save_users(users)

    tx = {"user": req.from_user, "type": "send", "to": receiver_name, "amount": req.amount, "time": time.time()}
    bc.chain[-1].data.append(tx)
    users[req.from_user]["coins"] -= req.amount
    users[receiver_name]["coins"] += req.amount
    save_users(users)
    bc.auto_block_if_needed()
    bc.save_chain()
    return {"message": f"{req.amount} coins sent to {receiver_name}"}

@app.get("/chain")
def view_blockchain():
    return [block.to_dict() for block in bc.chain]
