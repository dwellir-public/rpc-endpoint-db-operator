import requests

def get_block_height_aptos(api_url):
    # Send a GET request to the API endpoint
    # Example: https://fullnode.devnet.aptoslabs.com/v1/spec#/operations/get_ledger_info
    response = requests.get(api_url)

    # Parse the JSON response to get the block height
    block_height = response.json()['block_height']
    return block_height


def get_eth_block_height_ethbased(api_url, chain_id=1):
    # Set headers for the request
    headers = {'Content-Type': 'application/json'}

    # Set up the JSON-RPC payload for the request
    payload = {
        'jsonrpc': '2.0',
        'method': 'eth_blockNumber',
        'params': [],
        'id': str({chain_id})
    }

    # Send a POST request to the Infura API endpoint with the payload
    response = requests.post(api_url.format(chain_id=chain_id), headers=headers, json=payload)

    print(response.json())

    # Parse the JSON response to get the block height
    block_height = int(response.json()['result'], 16)

    return block_height



if __name__ ==  "__main__":
    
    api_url = 'https://fullnode.devnet.aptoslabs.com/v1/'
    print(f"Testing {api_url}")
    block_height = get_block_height_aptos(api_url)
    print('The current block height of the Aptos blockchain is:', block_height)
    api_url = "http://192.168.211.25:8545"
    block_height = get_eth_block_height_ethbased(api_url, chain_id=1)
    print(f'The current block height of the {api_url} blockchain is:', block_height)
