import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
import json
import sqlite3
import time
from urllib.request import urlopen
from datetime import datetime
import aiohttp
from async_timeout import timeout

import requests
import simplejson
import websockets
from websockets.exceptions import ConnectionClosedError, InvalidStatusCode
from requests.exceptions import ConnectionError, Timeout
from asyncio.exceptions import TimeoutError

# Description:
#
#  This script creates a database to hold metadata about API endpoints.
#  After run, the created database has information about which RPC endpoints
#  is "OK" and that subsequently can be used.
#
#  Example queries:
#  $ sqlite rpc_database.db
#  
# ## Get all OK to use API endpoints:
#  sqlite> SELECT * from rpcs where networkStatus == "OK" limit 3;
#          2|1284|https://rpc.api.moonbeam.network|1.59110355377197|3446153|OK
#          4|55555|https://rei-rpc.moonrhythm.io|1.83417654037476|89618|OK
#          5|10000|https://smartbch.greyh.at|2.22833704948425|9399670|OK
#
# ## Get all some data about API endpoints that was responding within 3 seconds:
#  sqlite> SELECT chains.chainId, rpcs.id,highestBlock,rpcs.latency from rpcs,chains where latency < 3;


DATABASE_NAME = "rpc_database.db"
JSON_DIR = "chains/_data/chains/"
REQUEST_TIMEOUT=10

def create_database():
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS chains
                 (chainId INTEGER PRIMARY KEY,
                  name TEXT,
                  chain TEXT,
                  icon TEXT,
                  features TEXT,
                  faucets TEXT,
                  nativeCurrency TEXT,
                  infoURL TEXT,
                  shortName TEXT,
                  networkId INTEGER,
                  slip44 INTEGER,
                  ens TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS rpcs
                 (id INTEGER PRIMARY KEY,
                  chainId INTEGER,
                  url TEXT,
                  latency FLOAT,
                  highestBlock INTEGER,
                  networkStatus TEXT,
                  FOREIGN KEY(chainId) REFERENCES chains(chainId))''')
    conn.commit()
    conn.close()


def insert_data_to_database():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # insert data into chains and rpcs tables
    for filename in os.listdir(JSON_DIR):
        if filename.endswith('.json'):
            with open(os.path.join(JSON_DIR, filename), "r") as f:

                data = json.load(f)

                # insert chain data into chains table
                chain_data = (
                    data.get('chainId'),
                    data.get('name'),
                    data.get('chain'),
                    data.get('icon'),
                    json.dumps(data.get('features', {})),
                    json.dumps(data.get('faucets', {})),
                    json.dumps(data.get('nativeCurrency', {})),
                    data.get('infoURL'),
                    data.get('shortName'),
                    data.get('networkId'),
                    data.get('slip44'),
                    json.dumps(data.get('ens', {}))
                )
                cursor.execute('''
                    INSERT INTO chains (
                        chainId,
                        name,
                        chain,
                        icon,
                        features,
                        faucets,
                        nativeCurrency,
                        infoUrl,
                        shortName,
                        networkId,
                        slip44,
                        ens
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', chain_data)

                # insert rpc data into rpcs table
                for rpc_url in data['rpc']:
                    rpc_data = (
                        None,
                        data['chainId'],
                        rpc_url,
                        None,
                        None,
                        None
                    )
                    cursor.execute('''
                        INSERT INTO rpcs (
                            id,
                            chainId,
                            url,
                            highestBlock,
                            latency,
                            networkStatus
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    ''', rpc_data)

    conn.commit()    # specify the directory containing the JSON files
    conn.close()


async def update_rpc_endpoint(rpc_id, url):
    """
    This async function updates the information of a single rpc_id.
    It needs to be async so that it can be called in parallel to speed up exectution.
    It manages ws/wss and http/https.
    It manages EIP155 (Ethereum chains) 
    """
    async with aiohttp.ClientSession() as session:
        try:
            # Make request to the RPC endpoint to retrieve data
            # Collect the latency
            start_time = time.time()
            protocol = url.split(':')[0]
            # Make an async call
            if protocol in ["ws", "wss"]:
                async with session.ws_connect(url, connect_timeout=REQUEST_TIMEOUT) as websocket:
                    request = json.dumps({'jsonrpc': '2.0', 'method': 'eth_blockNumber', 'params': [], 'id': 1})
                    try:
                        async with timeout(REQUEST_TIMEOUT):
                            await websocket.send_str(request)
                            response = await websocket.receive_str()
                            print(f"{url} took {time.time() - start_time:.2f} seconds to establish connection")
                    except asyncio.TimeoutError:
                        print(f"WebSocket connection to {url} timed out")
                        return
                    response_dict = json.loads(response)
            else:
                async with session.post(url, json={'jsonrpc': '2.0', 'method': 'eth_blockNumber', 'params': [], 'id': 1}, timeout=REQUEST_TIMEOUT) as resp:
                    try:
                        async with timeout(REQUEST_TIMEOUT):
                            response_dict = await resp.json()
                    except asyncio.TimeoutError:
                        print(f"HTTP POST request to {url} timed out")
                        return

            response_time = time.time() - start_time

            # parse the response JSON to get the latest block number
            if 'result' in response_dict:
                latest_block = int(response_dict['result'], 16)
            else:
                raise KeyError("Expected key 'result' not found in response_dict.")

            # update the 'rpc' table with the latest data
            print(f"rpcId: {rpc_id} {url} UP at block: {latest_block}")
            conn = sqlite3.connect(DATABASE_NAME)
            c = conn.cursor()
            c.execute('UPDATE rpcs SET highestBlock=?, latency=?, networkStatus=? WHERE id=?',
                      (latest_block, response_time, 'OK', rpc_id))
            conn.commit()
            conn.close()

        except (ConnectionError, InvalidStatusCode, Timeout) as e:
            print(f"Error connecting to {url}: {e}")
            # update the 'rpc' table with the latest data
            conn = sqlite3.connect(DATABASE_NAME)
            c = conn.cursor()
            c.execute('UPDATE rpcs SET networkStatus=? WHERE id=?',
                      ('DOWN', rpc_id))
            conn.commit()
            conn.close()
        except (Exception) as e:
            print(f"Something bogus with {url}: {e}")
            # update the 'rpc' table with the latest data
            conn = sqlite3.connect(DATABASE_NAME)
            c = conn.cursor()
            c.execute('UPDATE rpcs SET networkStatus=? WHERE id=?',
                      ('ERROR', rpc_id))
            conn.commit()
            conn.close()
        finally:
            return

async def update_rpc_data_in_database():
    # connect to the database
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()

    # get the total number of RPC requests to be processed
    c.execute('SELECT COUNT(*) FROM rpcs')
    count = c.fetchone()[0]
    total_requests = count

    # create a task for each chain and its corresponding RPC endpoints
    tasks = []

    completed_requests = 0
    
    # retrieve all RPC endpoints 
    c.execute('SELECT DISTINCT id, url, chainId FROM rpcs')
    rpc_rows = c.fetchall()

    with ThreadPoolExecutor(max_workers=10) as executor:
        # submit a task for each RPC endpoint request
        for rpc_id, url, chain_id in rpc_rows:
            print(f"Adding to task {chain_id} url: {url}")
            tasks.append(asyncio.ensure_future(update_rpc_endpoint(rpc_id, url)))

    # track progress and print status update
    for coro in asyncio.as_completed(tasks):
        try:
            result = await coro
            completed_requests += 1
            print(f"================== Processed {completed_requests}/{total_requests} RPC requests", end='\r')
        except Exception as e:
            print("============= ERROR ===============")

    # execute all tasks concurrently using asyncio
    await asyncio.gather(*tasks)

    # When all chains have been processed, close the database connection.
    conn.close()

async def main():
    await update_rpc_data_in_database()


    

if __name__ == '__main__':

    # create the database tables if they don't already exist
    create_database()

    # insert the data from the JSON files into the database
    insert_data_to_database()

    # Run the main function within an asyncio event loop
    # asyncio.run(main())


    # update singe value
    # update_single_rpc_data_in_database(1)

    # update the 'rpc' table with the latest data
    # asyncio.run( update_rpc_data_in_database())
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())