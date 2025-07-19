from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import json, os, time, hashlib, math
from typing import List, Dict

app = FastAPI()
CHAIN_FILE = "blockchain.json"
USER_FILE = "users.json"

# ----------------- Blockchain Classes ------------------

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
            with open(CHAIN_FILE, "r") as f:
                data = json.load(f)
                self.chain = [
                    Block(d["index"], d["prev_hash"], d["timestamp"], d["data"])
                    for d in data
                ]
        else:
            self.create_genesis_block()

    def auto_block_if_needed(self):
        users = load_users()
        total_coins = sum(user["balance"] for user in users.values())
        expected_blocks = math.floor(total_coins / 1000)
        while len(self.chain) - 1 < expected_blocks:
            self.add_block([])

# ----------------- User Handling ------------------

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
            "balance": 0
        }
        save_users(users)
    return users[username]

def find_user_by_address(address):
    users = load_users()
    for name, data in users.items():
        if data["address"] == address:
            return name
    return None

# ----------------- API Schemas ------------------

class JoinRequest(BaseModel):
    username: str

class BuyRequest(BaseModel):
    username: str
    amount: int

class SendRequest(BaseModel):
    from_user: str
    to: str
    amount: int

# ----------------- Blockchain Logic ------------------

bc = Blockchain()

@app.post("/join")
def join(req: JoinRequest):
    user = get_or_create_user(req.username)
    return {"message": "User joined", "user": user}

@app.get("/wallet/{username}")
def get_wallet(username: str):
    users = load_users()
    if username not in users:
        raise HTTPException(status_code=404, detail="User not found")
    return users[username]

@app.post("/buy")
def buy(req: BuyRequest):
    users = load_users()
    user = get_or_create_user(req.username)
    users[req.username]["balance"] += req.amount
    tx = {"from": "mint", "to": req.username, "amount": req.amount, "timestamp": time.time()}
    bc.chain[-1].data.append(tx)
    save_users(users)
    bc.auto_block_if_needed()
    return {"message": f"{req.amount} coins minted", "user": users[req.username]}

@app.post("/send")
def send(req: SendRequest):
    users = load_users()
    sender = get_or_create_user(req.from_user)

    if sender["balance"] < req.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    recipient_name = req.to if req.to in users else find_user_by_address(req.to)
    if not recipient_name:
        recipient_name = f"user_{req.to[:6]}"
        users[recipient_name] = {"address": req.to, "balance": 0}

    users[req.from_user]["balance"] -= req.amount
    users[recipient_name]["balance"] += req.amount
    tx = {"from": req.from_user, "to": recipient_name, "amount": req.amount, "timestamp": time.time()}
    bc.chain[-1].data.append(tx)

    save_users(users)
    bc.auto_block_if_needed()
    return {"message": f"{req.amount} coins sent to {recipient_name}"}

@app.get("/chain")
def get_chain():
    return [block.to_dict() for block in bc.chain]
