import asyncio
from rpc_utils import get_aptos, get_ethereum, get_substrate, fetch_all_info

# Example usage:
all_url_api_tuples = [
    ('https://aptos-mainnet-rpc.allthatnode.com/v1', 'aptos'),
    ('wss://rpc.polkadot.io', 'substrate'),
    ('https://ethereum.publicnode.com', 'ethereum')
]

loop = asyncio.get_event_loop()
results = loop.run_until_complete(fetch_all_info(all_url_api_tuples))

# Print the results
for r in results:
    print(r)
