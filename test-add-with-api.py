#!/bin/env python3

import requests

# Define the API endpoint
url = 'http://localhost:5000/create'

# Define the chain data to add
chains = [
    {
        'chain_id': 1,
        'chain_name': 'Ethereum',
        'urls': ['https://ethereum.com', 'wss://eth.se']
    },
    {
        'chain_id': 2,
        'chain_name': 'Bitcoin',
        'urls': ['https://bitcoin.com', 'wss://btc.se']
    },
    {
        'chain_id': 3,
        'chain_name': 'Polkadot',
        'urls': ['https://polkadot.com', 'wss://dot.se']
    }
]

# Add the chains to the database
for chain in chains:
    response = requests.post(url, json=chain)
    if response.status_code == 201:
        print(f'Added chain with ID {response.json()["id"]}')
    else:
        print(f'Error adding chain: {response.json()}')

# Print all chains
response = requests.get('http://localhost:5000/all')
if response.status_code == 200:
    for chain in response.json():
        print(f'Chain {chain["chain_name"]} with ID {chain["chain_id"]} has URLs:')
        for url in chain['urls']:
            print(f' - {url}')
else:
    print(f'Error retrieving chains: {response.json()}')

# Delete all chains
for chain in chains:
    response = requests.delete(f'http://localhost:5000/delete/{chain["chain_id"]}')
    if response.status_code == 200:
        print(f'Deleted chain with ID {chain["chain_id"]}')
    else:
        print(f'Error deleting chain: {response.json()}')
