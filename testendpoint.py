import asyncio
import time
import aiohttp
from rpc_utils import get_aptos, get_ethereum, get_substrate

async def get_substrate_blockheight_wss_lat(api_url):
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
            highest_block = None
            latency = None
            http_code = None
            exit_code = 1
        return highest_block, latency, http_code, exit_code

async def main():
    uri = "wss://rpc.polkadot.io"
    block_height, lat, hc,ec = await get_substrate(uri)
    print(f"Latest block height: {block_height} time_total: {lat} http_code: {hc} error_code: {ec}")

    uri = "wss://ethereum.publicnode.com"
    block_height, lat, hc,ec = await get_ethereum(uri)
    print(f"Latest block height: {block_height} time_total: {lat} http_code: {hc} error_code: {ec}")

if __name__ == "__main__":
    asyncio.run(main())