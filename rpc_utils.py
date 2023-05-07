import time
import requests
from urllib.parse import urlparse
from requests.exceptions import RequestException, Timeout, ConnectionError, HTTPError
from urllib3.exceptions import NameResolutionError
import asyncio
import aiohttp

def is_valid_url(url):
    valid_schemes = ['ws', 'wss', 'http', 'https']
    parsed_url = urlparse(url)
    return parsed_url.scheme in valid_schemes

async def get_aptos(api_url):
    async with aiohttp.ClientSession() as session:
        try:
            start_time = time.monotonic()
            async with session.get(api_url) as resp:
                end_time = time.monotonic()
                response = await resp.json()
            highest_block = int(response['block_height'])
            latency = (end_time - start_time)
            http_code = resp.status
            exit_code = 0
        except aiohttp.ClientError as e:
            return None,None,None,None
        return highest_block, latency, http_code, exit_code


async def get_substrate(api_url):
    async with aiohttp.ClientSession() as session:
        try:
            start_time = time.monotonic()
            async with session.post(api_url, json={"jsonrpc":"2.0","id":1,"method":"chain_getHeader","params":[]}) as resp:
                end_time = time.monotonic()
                response = await resp.json()
            highest_block = int(response['result']['number'], 16)
            latency = (end_time - start_time)
            http_code = resp.status
            exit_code = 0
        except aiohttp.ClientError as e:
            return None,None,None,None
        return highest_block, latency, http_code, exit_code


async def get_ethereum(api_url, chain_id=1):
    async with aiohttp.ClientSession() as session:
        try:
            start_time = time.monotonic()
            async with session.post(api_url, json={'jsonrpc': '2.0', 'method': 'eth_blockNumber', 'params': [], 'id': str({chain_id}) }) as resp:
                end_time = time.monotonic()
                response = await resp.json()
            
            print(response)
            highest_block = int(response['result'], 16)
            latency = (end_time - start_time)
            http_code = resp.status
            exit_code = 0
        except aiohttp.ClientError as e:
            return None,None,None,None
        
        return highest_block, latency, http_code, exit_code

##########################################


async def query_for_latency_and_blockheight(url, api_type):
    """
    Performs query of a remote API with requests.
    """
    if not is_valid_url(url):
        raise ValueError('Invalid URL')

    try:
        if api_type == 'aptos':
            latest_block_height, time_total, http_code, exit_code = await get_aptos(url)
        elif api_type == "substrate":
            latest_block_height, time_total, http_code, exit_code = await get_substrate(url)
        elif api_type == "ethereum":
            latest_block_height, time_total, http_code, exit_code = await get_ethereum(url)
        else:
            print(f"Unrecognized api: {api_type}")
            raise ValueError(f"Unrecognized api: {api_type}")
        
    except (requests.RequestException, requests.Timeout, ConnectionError, requests.HTTPError, NameResolutionError) as e:
        print(f"Something went wrong query_for_latency_and_blockheight: ", e)
        time_total = 0
        http_code = 0
        exit_code = 1
        latest_block_height = 0

    info = {
        'http_code': http_code,
        'time_total': time_total,
        'exitcode': exit_code,
        'latest_block_height': latest_block_height
    }

    return info
