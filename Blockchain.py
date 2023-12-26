

import sys
import hashlib
import json
import requests
from urllib.parse import urlparse
from time import time
from uuid import uuid4
from flask import Flask, jsonify, render_template, request

class Blockchain(object):
    
    difficulty = "0000"

    def hash_block(self, block):
        block_encoded = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_encoded).hexdigest()    
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()
        
        genesis_hash = self.hash_block({'index': 0, 'timestamp': time(), 'transactions': [], 'nonce': 100}) # Create a proper genesis block
        self.append_block(hash_of_previous_block=genesis_hash, nonce=self.proof_of_work(0, genesis_hash, []))

        
        
    def proof_of_work(self, index, hash_of_previous_block, transactions):
        nonce = 0
        hash=self.valid_proof(index, hash_of_previous_block, transactions, nonce) 
        while hash[0]==False:
            nonce += 1
            hash=self.valid_proof(index, hash_of_previous_block, transactions, nonce) 
        return nonce,hash[1]
    
    def valid_proof(self, index, hash_of_previous_block, transactions, nonce):
        content = f'{index}{hash_of_previous_block}{transactions}{nonce}'.encode()
        content_hash = hashlib.sha256(content).hexdigest()
        return [content_hash[:len(self.difficulty)] == self.difficulty,content_hash]
    
    def append_block(self, nonce, hash_of_previous_block):
        block = {
            'index': len(self.chain),
            'timestamp': time(),
            "Current_hash":nonce[1],
            'transactions': self.current_transactions.copy(),
            'nonce': nonce[0],
            'hash_of_previous_block': hash_of_previous_block
        }
        self.current_transactions = []
        self.chain.append(block)
        return block
    
    def add_transaction(self, sender, recipient, amount):
        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount
        })

    @property
    def last_block(self):
        return self.chain[-1]
    
    def add_node(self, address):
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)
        print(parsed_url.netloc)

    def valid_chain(self, chain):
        last_block = chain[0]
        current_index = 1
        
        while current_index < len(chain):
            block = chain[current_index]

            if block['hash_of_previous_block'] != self.hash_block(last_block):
                return False
            if not self.valid_proof(last_block['index'], last_block['hash_of_previous_block'], block['transactions'], block['nonce']):
                return False
            last_block = block
            current_index += 1
        return True
    
    def update_blockchain(self, chain):
        neighbours = self.nodes
        new_chain = None
        max_length = len(self.chain)
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')
            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        if new_chain:
            self.chain = new_chain
            return True
        return False
    
    


app = Flask(__name__)
node_identifier = str(uuid4()).replace('-', '')
blockchain = Blockchain()

@app.route('/')
def index():
    return render_template('index.html')  # Assuming your HTML file is named 'index.html'


@app.route('/blockchain', methods=['GET'])
def full_chain():
    # Render the blockchain view page
    return render_template('blockchain.html')

@app.route('/get_blockchain', methods=['GET'])
def get_blockchain():
    # Endpoint to return blockchain data in JSON
    chain_data = []
    for block in blockchain.chain:
        block_data = {
            'index': block['index'],
            'timestamp': block['timestamp'],
            'nonce': block['nonce'],
            'hash_of_previous_block': block['hash_of_previous_block'],  # Make sure this is correct
            'transactions': block['transactions'],
            'Current_hash':block['Current_hash']
        }
        chain_data.append(block_data)

    response = {
        'chain': chain_data,
        'length': len(chain_data)
    }
    return jsonify(response)


@app.route('/mine', methods=['GET'])
def mine_block():
    blockchain.add_transaction(
        sender="0", # Indicating this is a mining reward
        recipient=node_identifier,
        amount=1,
    )
    index = len(blockchain.chain)
    last_block=blockchain.last_block["Current_hash"]
    nonce = blockchain.proof_of_work(index, last_block, blockchain.current_transactions)
    
    block = blockchain.append_block(nonce, last_block)
    response = {
        "message": "New Block Mined",
        "index": block["index"],
        "transactions": block["transactions"],
        "nonce": block["nonce"],
        "Current_hash":block["Current_hash"],
        "hash_of_previous_block":block["hash_of_previous_block"],
    }
    return jsonify(response), 200


@app.route('/mine-page', methods=['GET'])
def mine_page():
    # This route just renders the static mine.html page
    return render_template('mine.html')

@app.route('/transactions/new', methods=['GET'])
def new_transaction_page():
    # Render the new transaction form page
    return render_template('new_transaction.html')

@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return jsonify({'message': "Missing values"}), 400
    index = blockchain.add_transaction(values['sender'], values['recipient'], values['amount'])
    response = {'message': f'Transaction will be added to Block {index}'}
    return jsonify(response), 201

@app.route('/nodes/register', methods=['GET'])
def register_nodes_page():
    # Render the register nodes form page
    return render_template('register_node.html')

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    nodes = values.get('nodes')
    if not nodes:
        return "Error: Please supply a valid list of nodes", 400
    for node in nodes:
        blockchain.add_node(node)
    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def resolve_nodes_page():
    # Render the resolve nodes page
    return render_template('resolve_nodes.html')


@app.route('/nodes/resolve', methods=['POST'])
def resolve_conflicts():
    # Your node resolution logic
    replaced = blockchain.resolve_conflicts()
    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }
    return jsonify(response), 200

@app.route('/nodes/list', methods=['GET'])
def list_nodes():
    nodes = list(blockchain.nodes)
    return render_template('nodes_list.html', nodes=nodes)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(sys.argv[1]))
    


