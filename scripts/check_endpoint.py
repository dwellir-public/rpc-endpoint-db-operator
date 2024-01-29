#!/usr/bin/env python3


import argparse
import time
import asyncio
import aiohttp
import websocket
import json
import json


def main():
    parser = argparse.ArgumentParser(description='Utility script to test that an endpoint is working')
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
        wss_urls = [url for url in urls if url.startswith("wss")]
        print(f"URL:s with wss URL: {len(wss_urls)}")
        for url in wss_urls:
            payload = {
                "jsonrpc": "2.0",
                "method": "chain_getHeader",
                "params": [],
                "id": 1
            }
            try:
                ws = websocket.create_connection(url)
                ws.send(json.dumps(payload))
                response = json.loads(ws.recv())
                print(response)
                ws.close()
                if not 'jsonrpc' in response.keys():
                    print(f'#> error for {url}')
                    print(f'URL {url} produced WS response={response}')
            except Exception as e:
                print(f'URL {url} failed WS connection: {e}')


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
