#!/usr/bin/env python3
"""A script to test and validate endpoints for use with the RPC endpoint DB charm.

Usage:
    python3 check_endpoint.py --url <URL>
    python3 check_endpoint.py --file <FILE>
    python3 check_endpoint.py --both

    --url: URL to test
    --file: File with URLs to test, in JSON format as a list where each field is a dict with the key "url"
            [{"url": "http://localhost:9933"}, {"url": "ws://localhost:9944"}]
    -http, --aiohttp: Test using aiohttp package
    -ws, --websocket: Test using websocket package
    --both: Test both packages
"""

import argparse
import asyncio
import json
import queue
import threading
import time

import aiohttp
import websocket


def main():
    parser = argparse.ArgumentParser(description='Utility script to test that an endpoint or a list of endpoitns are working')
    parser.add_argument('--url', type=str, help='URL to test')
    parser.add_argument('--file', type=str, help='File with URLs to test')
    protocol = parser.add_mutually_exclusive_group(required=True)
    protocol.add_argument('-http', '--aiohttp', action="store_true", help='Make requests using aiohttp')
    protocol.add_argument('-ws', '--websocket', action="store_true", help='Make requests using the websocket package')
    protocol.add_argument('--both', action="store_true", help='Make requests using both of the above')
    args = parser.parse_args()

    urls = []
    if args.url:
        urls.append(args.url)
    if args.file:
        with open(args.file, 'r') as f:
            json_data = f.read()
            data = json.loads(json_data)
        file_urls = [item['url'] for item in data]
        urls.extend(file_urls)
    print(f"URL:s found from input: {len(urls)}")

    if args.aiohttp or args.both:
        print("> aiohttp")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(fetch(urls))

    if args.websocket or args.both:
        print("> websocket")
        wss_urls = [url for url in urls if url.startswith("ws")]
        print(f"#> URL:s with ws URL: {len(wss_urls)}")
        payload = {
            "jsonrpc": "2.0",
            "method": "chain_getHeader",
            "params": [],
            "id": 1
        }
        err_counter = []
        for url in wss_urls:
            try:
                print(f'#> testing {url}')
                ws_queue = queue.Queue()
                # Create a thread to time limit the ws connection
                thread = threading.Thread(target=send_payload, args=(url, payload, ws_queue), daemon=True)
                thread.start()
                thread.join(timeout=3)  # 3 seconds timeout for the thread to set up the ws connection
                if thread.is_alive():
                    print("# #> Send operation timed out")
                    err_counter.append(url)
                else:
                    if not ws_queue.empty():
                        ws, status = ws_queue.get()
                        if status == 1:
                            err_counter.append(url)
                        elif ws is not None:
                            response = json.loads(ws.recv())
                            print(response)
                            ws.close()
                            if 'jsonrpc' not in response.keys():
                                print(f'# #> error in response for {url}')
                                print(f'URL {url} produced WS response={response}')
                                err_counter.append(url)
                        else:
                            print(f'# #> Unkown error for {url}')
                            err_counter.append(url)
            except Exception as e:
                print(f'URL {url} failed WS connection: {e}')

        print(f"#> Errors during run: {len(err_counter)}")
        print("#> URL:s failing:")
        for url in err_counter:
            print(f" > {url}")


def send_payload(url: str, payload, ws_queue):
    try:
        ws = websocket.create_connection(url)
        ws.send(json.dumps(payload))
        ws_queue.put((ws, 0))  # 0 indicates success
    except (websocket.WebSocketBadStatusException, websocket._exceptions.WebSocketException) as e:
        print(f'# #> WebSocket connection failed for {url} with error: {e}')
        ws_queue.put((None, 1))  # 1 indicates an error


async def get_substrate(api_url):
    async with aiohttp.ClientSession() as session:
        try:
            start_time = time.monotonic()
            response = None
            if "http" in api_url:
                async with session.post(api_url, json={"jsonrpc": "2.0", "id": 1, "method": "chain_getHeader", "params": []}) as resp:
                    end_time = time.monotonic()
                    response = await resp.json()
                    http_code = resp.status
            elif "ws" in api_url:
                payload = {
                    "jsonrpc": "2.0",
                    "method": "chain_getHeader",
                    "params": [],
                    "id": 1
                }
                async with session.ws_connect(api_url) as ws:
                    end_time = time.monotonic()
                    await ws.send_json(payload)
                    resp = await ws.receive()
                    response = json.loads(resp.data)
                http_code = 0
            print(response)
            highest_block = int(response['result']['number'], 16)
            latency = (end_time - start_time)
            exit_code = 0
        except aiohttp.ClientError as e:
            print(f"aiohttp.ClientError in get_substrate for url {api_url}", response, e)
            return {'latest_block_height': None, 'time_total': None, 'http_code': None, 'exit_code': None}
        except Exception as ee:
            print(f"{ee.__class__.__name__} in get_substrate for url {api_url}", response, ee)
            return {'latest_block_height': None, 'time_total': None, 'http_code': None, 'exit_code': None}

        info = {
            'http_code': http_code,
            'time_total': latency,
            'exit_code': exit_code,
            'latest_block_height': highest_block
        }

        return info


async def request(url: str):
    return await get_substrate(url)


async def fetch(urls: list[str]):
    loop = asyncio.get_event_loop()
    tasks = []
    for url in urls:
        tasks.append(loop.create_task(request(url)))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results


if __name__ == '__main__':
    main()
