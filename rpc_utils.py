import requests
from urllib.parse import urlparse
from requests.exceptions import RequestException, Timeout, ConnectionError, HTTPError
from urllib3.exceptions import NameResolutionError

def is_valid_url(url):
    valid_schemes = ['ws', 'wss', 'http', 'https']
    parsed_url = urlparse(url)
    return parsed_url.scheme in valid_schemes

def get_block_height_aptos(api_url):
    # Send a GET request to the API endpoint
    # Example: https://fullnode.devnet.aptoslabs.com/v1/spec#/operations/get_ledger_info
    response = requests.get(api_url)
    # Check if the response contains block height
    if 'block_height' not in response.json():
        print(f"Error: Block height not found in response from {api_url}")
        return None

    # Try to convert the block height to an integer
    try:
        block_height = int(response.json()['block_height'])
    except (ValueError, TypeError):
        print(f"Error: Invalid block height in response from {api_url}")
        return None

    return block_height


def get_eth_block_height_ethbased(api_url, chain_id=1):
    # Set headers for the request
    headers = {'Content-Type': 'application/json'}
    # Set up the JSON-RPC payload for the request
    payload = {'jsonrpc': '2.0', 'method': 'eth_blockNumber', 'params': [], 'id': str({chain_id}) }
    # Send a POST request to the API endpoint with the payload
    response = requests.post(api_url.format(chain_id=chain_id), headers=headers, json=payload)
    try:
        # Parse the JSON response to get the block height
        block_height = int(response.json()['result'], 16)
        return block_height
    except (KeyError, ValueError):
        return None
    
##########################################


def query_for_latency_and_blockheight(url, api_type):
    """
    Performs query of a remote API with requests.
    """
    if not is_valid_url(url):
        raise ValueError('Invalid URL')

    if api_type == 'ethereum':
        data = '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
    elif api_type == 'substrate':
        data = '{"jsonrpc":"2.0","method":"chain_getHeader","params":[],"id":1}'
    elif api_type == 'aptos':
        # Also, uses the http GET method
        data = '{"jsonrpc":"2.0","method":"block_number","params":[],"id":1}'
    else:
        print(f"Unrecognized api: {api_type}")
        raise ValueError(f"Unrecognized api: {api_type}")

    headers = {
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Keep-Alive': 'timeout=5, max=20'
        }

    try:
        if api_type == 'aptos':
            response = requests.get(url, headers=headers, data=data)
            response.raise_for_status()
            latest_block_height = int(response.json()['block_height'])
        else:
            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()
            result = response.json().get('result')
            latest_block_height = int(result, 16) if api_type == 'ethereum' else int(result['number'], 16)
        
        # Latency, isn't actually getting the same data as with curl -w
        time_total = response.elapsed.total_seconds()
        http_code = response.status_code
        ssl_verify_result = 1 if response.url.startswith('https') or response.url.startswith('wss') else 0
        time_redirect = response.history[0].elapsed.total_seconds() if response.history else 0
        time_namelookup = response.elapsed.total_seconds() - time_total
        time_connect = response.elapsed.total_seconds() - time_total
        time_appconnect = 0
        time_pretransfer = response.elapsed.total_seconds() - time_total
        time_starttransfer = response.elapsed.total_seconds() - time_total
        exit_code = 0
        error_msg = ''
    except (requests.RequestException, requests.Timeout, ConnectionError, requests.HTTPError, NameResolutionError) as e:
    #except (requests.exceptions.RequestException, requests.exceptions.NameResolutionError, ValueError) as e:
        print(f"Failed getting into from {url}")
        time_total = 0
        http_code = 0
        ssl_verify_result = 0
        time_redirect = 0
        time_namelookup = 0
        time_connect = 0
        time_appconnect = 0
        time_pretransfer = 0
        time_starttransfer = 0
        exit_code = 1
        error_msg = ''
        latest_block_height = 0

    info = {
        'http_code': http_code,
        'ssl_verify_result': ssl_verify_result,
        'time_redirect': time_redirect,
        'time_namelookup': time_namelookup,
        'time_connect': time_connect,
        'time_appconnect': time_appconnect,
        'time_pretransfer': time_pretransfer,
        'time_starttransfer': time_starttransfer,
        'time_total': time_total,
        'exitcode': exit_code,
        'errormsg': error_msg,
        'latest_block_height': latest_block_height
    }

    return info
