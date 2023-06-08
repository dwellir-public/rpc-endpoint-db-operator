#!/usr/bin/env python3

import asyncio
import json
import logging
from color_logger import ColoredFormatter
import sys
from pathlib import Path
import requests
import warnings
import argparse
import time
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_utils import new_block_height_request_point, test_influxdb_connection, fetch_all_info

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
formatter = ColoredFormatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# TODO: add block height diff calculation to DB update procedure
# TODO: add more settings to config; update interval


def main():
    parser = argparse.ArgumentParser(description='Continuously update the InfluxDB specified in the config file')
    parser.add_argument('config_file', type=str, help="The file with the target database's config", default='config.json')
    args = parser.parse_args()

    if not (Path.cwd() / args.config_file).exists():
        raise FileNotFoundError
    with open(args.config_file, encoding='utf-8') as f:
        config = json.load(f)

    # TODO: add validation of config through schema? rpc api and influxdb required, cache age and update interval optional

    influxdb = {
        'url': config['INFLUXDB_URL'],
        'token': config['INFLUXDB_TOKEN'],
        'org': config['INFLUXDB_ORG'],
        'bucket': config['INFLUXDB_BUCKET']
    }

    # Test connection to influx before attempting to start.
    if not test_influxdb_connection(influxdb['url'], influxdb['token'], influxdb['org']):
        logger.error("Couldn't connect to influxdb at url %s\nExiting.", influxdb['url'])
        sys.exit(1)

    with warnings.catch_warnings() as w:
        loop = asyncio.get_event_loop()
        if "no current event loop" in str(w):
            logger.info("First startup, starting new event loop.")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

    while True:
        # Get all RPC endpoints from all chains.
        # Place them in a list with their corresponding class.
        # This is all the endpoints we are to query and update the influxdb with.
        # all_url_api_tuples = get_all_endpoints_from_api(rpc_flask_api)
        all_url_api_tuples = load_endpoints(config['RPC_FLASK_API'], config['CACHE_MAX_AGE'])

        info = loop.run_until_complete(fetch_all_info(all_url_api_tuples))

        for endpoint, info_dict in zip(all_url_api_tuples, info):
            if info_dict:
                bcp = new_block_height_request_point(chain=endpoint[0], url=endpoint[1], api=endpoint[2], data=info_dict)
                records = []
                records.append(bcp)
                try:
                    exitcode = int(info_dict.get('exitcode', -1)) if info_dict.get('exitcode') is not None else None
                    if exitcode != 0:
                        logger.warning("Non-zero exit_code found for %s. This is an indication that the endpoint isn't healthy.", endpoint)
                    elif exitcode is None:
                        logger.warning("Exit code is None for %s. I will not add this datapoint.", endpoint)
                    else:
                        logger.info("Writing to influx %s: Data: %s", endpoint, info_dict)
                        write_to_influxdb(influxdb['url'], influxdb['token'], influxdb['org'], influxdb['bucket'], records)

                except Exception as e:
                    logger.error("Something went wrong while trying to write to influxdb %s: %s %s", endpoint, info_dict, str(e))
            else:
                logger.warning("Couldn't get information from %s. Skipping.", endpoint)

        # Wait for 5 seconds before running again. Allows us to see what goes on.
        # Possibly we can remove this later.
        time.sleep(5)


# Define function to write data to InfluxDB
def write_to_influxdb(url: str, token: str, org: str, bucket: str, records: list) -> None:
    try:
        client = InfluxDBClient(url=url, token=token, org=org)
        write_api = client.write_api(write_options=SYNCHRONOUS)
        write_api.write(bucket=bucket, record=records)
    except Exception as e:
        logger.critical("Failed writing to influx. This shouldn't happen. %s",  str(e))
        sys.exit(1)


def load_endpoints(rpc_flask_api: str, cache_refresh_interval: int = 60) -> list:
    """Load endpoints from cache or refresh if cache is stale."""

    # Load cached values from file
    try:
        with open('cache.json', 'r', encoding='utf-8') as f:
            all_url_api_tuples, last_cache_refresh = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning('Could not load values from cache.json')
        all_url_api_tuples, last_cache_refresh = None, 0

    # Check if cache is stale
    if time.time() - last_cache_refresh > cache_refresh_interval:
        refresh_cache = True
    else:
        diff = time.time() - last_cache_refresh
        remains = cache_refresh_interval - diff
        logger.info("Cache will be updated in: %s", remains)
        refresh_cache = False

    if refresh_cache:
        try:
            logger.info("Updating cache from endpoints API")
            all_url_api_tuples = get_all_endpoints_from_api(rpc_flask_api)
            last_cache_refresh = time.time()

            # Save updated cache to file
            with open('cache.json', 'w', encoding='utf-8') as f:
                json.dump((all_url_api_tuples, last_cache_refresh), f)

        except Exception as e:
            # Log the error
            logger.error("An error occurred while getting endpoints: %s", str(e))

            # Load the previous cache value
            with open('cache.json', 'r', encoding='utf-8') as f:
                all_url_api_tuples, last_cache_refresh = json.load(f)

    else:
        logger.info("Using cached endpoints")

    return all_url_api_tuples


def get_all_endpoints_from_api(rpc_flask_api: str) -> list:
    url_api_tuples = []
    all_chains = requests.get(f'{rpc_flask_api}/all/chains', timeout=3)
    for chain in all_chains.json():
        chain_info = requests.get(f'{rpc_flask_api}/chain_info?chain_name={chain["name"]}', timeout=1)
        for url in chain_info.json()['urls']:
            url_api_tuples.append((chain_info.json()['chain_name'], url, chain_info.json()['api_class']))
    return url_api_tuples


if __name__ == '__main__':
    main()
