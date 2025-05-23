#!/usr/bin/env python3

"""Utility script to interact with the RPC endpoint database.

Can access the endpoint database through two means:
- Using the Flask API wrapping the database
- Directly accessing the database file, if it's available locally
"""

import argparse
import json
import sqlite3
from pathlib import Path

import requests
import websocket

DEFAULT_URL = 'http://localhost:8000'

PATH_DIR = Path(__file__).parent.absolute()
PATH_DEFAULT_AUTH_PW = PATH_DIR / 'auth_password'
PATH_DEFAULT_DB = PATH_DIR / 'live_database.db'
PATH_DEFAULT_DB_JSON_DIR = PATH_DIR / 'db_json'
PATH_DEFAULT_CHAINS = PATH_DEFAULT_DB_JSON_DIR / 'chains.json'
PATH_DEFAULT_RPC_URLS = PATH_DEFAULT_DB_JSON_DIR / 'rpc_urls.json'
PATH_DEFAULT_IN_DIR = PATH_DIR / 'in'
PATH_DEFAULT_IN_CHAINS = PATH_DEFAULT_IN_DIR / 'chains.json'
PATH_DEFAULT_IN_RPC_URLS = PATH_DEFAULT_IN_DIR / 'rpc_urls.json'
PATH_DEFAULT_OUT_DIR = PATH_DIR / 'out'

TABLE_CHAINS = 'chains'
TABLE_RPC_URLS = 'rpc_urls'


def main() -> None:
    parser = argparse.ArgumentParser(description='Utility script to work with an SQLite database served by a Flask API')
    subparsers = parser.add_subparsers()
    # Import
    parser_import = subparsers.add_parser('import', help='Import data into a database from JSON files')
    parser_import.add_argument('--chains', type=str,
                               help=f'JSON file with chains to import, default={PATH_DEFAULT_IN_CHAINS}')
    parser_import.add_argument('--rpc_urls', type=str,
                               help=f'JSON file with RPC URL:s to import, default={PATH_DEFAULT_IN_RPC_URLS}')
    parser_import.set_defaults(func=import_data, chains=str(PATH_DEFAULT_IN_CHAINS), rpc_urls=str(PATH_DEFAULT_IN_RPC_URLS))
    import_target_group = parser_import.add_mutually_exclusive_group(required=True)
    import_target_group.add_argument('-db', '--target_db', type=str, help='The path to the local database file')
    import_target_group.add_argument('-url', '--target_url', type=str, help='The url for the API of the database')
    # Export
    parser_export = subparsers.add_parser('export', help='Export data from a database to JSON files')
    parser_export.add_argument('--target', type=str,
                               help=f'Directory the JSON:s will exported to, default={PATH_DEFAULT_OUT_DIR}')
    parser_export.add_argument('--force', action='store_true', help='Force export to overwrite files without asking')
    parser_export.set_defaults(func=export_data, target=str(PATH_DEFAULT_OUT_DIR))
    export_target_group = parser_export.add_mutually_exclusive_group(required=True)
    export_target_group.add_argument('-db', '--source_db', type=str, help='The path to the local database file')
    export_target_group.add_argument('-url', '--source_url', type=str, help='The URL for the API of the database')

    # Make an RPC request
    parser_request = subparsers.add_parser('request', help='Send a request to the Flask API serving the database')
    parser_request.add_argument('--url', type=str, help='The url for the API of the database')
    parser_request.add_argument('--auth-pw', type=str, help='The authentication password to get the access token for the API')
    parser_request.set_defaults(url=DEFAULT_URL)
    request_sp = parser_request.add_subparsers()
    # Chains
    request_chains = request_sp.add_parser('chains', help='Get all chains')
    request_chains.set_defaults(func=get_all_chains)
    request_add_chain = request_sp.add_parser('add_chain', help='Add a URL to the database')
    request_add_chain.add_argument('chain', type=str, help='The name of the chain')
    request_add_chain.add_argument('api_class', type=str, help='The API class used by the chain')
    request_add_chain.set_defaults(func=add_chain)
    request_delete_chain = request_sp.add_parser('delete_chain', help='Delete a chain from the database')
    request_delete_chain.add_argument('chain', type=str, help='The name of the chain that should be deleted')
    request_delete_chain.set_defaults(func=delete_chain)
    # RPC URL:s
    request_rpc_urls = request_sp.add_parser('rpc_urls', help='Get all RPC URL:s')
    request_rpc_urls.set_defaults(func=get_all_rpc_urls)
    request_add_rpc = request_sp.add_parser('add_rpc', help='Add a URL to the database')
    request_add_rpc.add_argument('chain', type=str, help='The name of the chain the RPC URL belongs to')
    request_add_rpc.add_argument('rpc', type=str, help='The RPC URL that should be added to the DB')
    request_add_rpc.set_defaults(func=add_rpc)
    request_delete_rpc = request_sp.add_parser('delete_rpc', help='Delete a URL from the database')
    request_delete_rpc.add_argument('rpc', type=str, help='The RPC URL that should be deleted from the DB')
    request_delete_rpc.set_defaults(func=delete_rpc)

    # Validate JSON files
    parser_json = subparsers.add_parser('json', help='Check and validate JSON files with chains and RPC:s')
    parser_json.add_argument('directory', type=str,
                             help=f'Directory containing the JSON files, default={PATH_DEFAULT_OUT_DIR}')
    parser_json.add_argument('-r', '--reverse', action='store_true', help='Reverse the order the list of RPC:s is parsed')
    parser_json.add_argument('-f', '--filter', type=str, help='Filter the list of chains to validate')
    parser_json.set_defaults(func=validate_json, directory=str(PATH_DEFAULT_OUT_DIR))

    args = parser.parse_args()
    args.func(args)


# # # IMPORT # # #

def import_data(args) -> None:
    print(f'Import source: chains file  {args.chains}')
    print(f'Import source: RPC URL file {args.rpc_urls}')
    chains = load_json_file(args.chains)
    rpc_urls = load_json_file(args.rpc_urls)
    if args.target_url:
        print(f'Import target: API at URL {args.target_url}')
        api_import_from_json_files(chains, rpc_urls, args.target_url)
    if args.target_db:
        print(f'Import target: database on path {args.target_db}')
        local_import_from_json_files(chains, rpc_urls, args.target_db)


def api_import_from_json_files(chains: dict, rpc_urls: dict, api_url: str) -> None:
    """Imports data from JSON files into an SQLite database.
    Assumes the JSON files has a specific format, see `db_json` folder in this repository.
    """
    authorization_header = get_auth_header(api_url)

    if chains:
        url_format = api_url + '/create_chain'
        unique_chain_counter = 0
        for chain in chains:
            response = requests.post(url_format, json=chain, headers=authorization_header, timeout=5)
            if response.status_code == 201:
                print(f'> Added chain {chain["name"]}')
            elif "UNIQUE constraint failed" in response.text:
                unique_chain_counter = unique_chain_counter + 1
            else:
                print(f"Error: {response.status_code}", response.text)
        if unique_chain_counter > 0:
            print(f"{unique_chain_counter} chains already existing in the database were skipped")

    if rpc_urls:
        url_format = api_url + '/create_rpc_url'
        unique_rpc_counter = 0
        for rpc_url in rpc_urls:
            response = requests.post(url_format, json=rpc_url, headers=authorization_header, timeout=5)
            if response.status_code == 201:
                print(f'> Added RPC URL {rpc_url["url"]}')
            elif "UNIQUE constraint failed" in response.text:
                unique_rpc_counter = unique_rpc_counter + 1
            else:
                print(f"Error: {response.status_code}", response.text)
        if unique_rpc_counter > 0:
            print(f"{unique_rpc_counter} RPC URL:s already existing in the database were skipped")


def local_import_from_json_files(chains: dict, rpc_urls: dict, db_file: str) -> None:
    """Imports data from JSON files into an SQLite database.
    Assumes the JSON files has a specific format, see `db_json` folder in this repository.
    """
    conn = sqlite3.connect(db_file)
    conn.execute('PRAGMA foreign_keys = ON')
    cursor = conn.cursor()

    if chains:
        unique_chain_counter = 0
        for entry in chains:
            name = entry['name']
            api_class = entry['api_class']
            query = f'INSERT INTO {TABLE_CHAINS} (name, api_class) VALUES (?, ?)'
            values = (name, api_class)
            try:
                cursor.execute(query, values)
                print(f'> Added chain {entry["name"]}')
            except sqlite3.IntegrityError as e:
                if "UNIQUE constraint failed" in str(e):
                    unique_chain_counter = unique_chain_counter + 1
        if unique_chain_counter > 0:
            print(f"{unique_chain_counter} chains already existing in the database were skipped")

    if rpc_urls:
        unique_rpc_counter = 0
        for entry in rpc_urls:
            url = entry['url']
            chain_name = entry['chain_name']
            query = f'INSERT INTO {TABLE_RPC_URLS} (url, chain_name) VALUES (?, ?)'
            values = (url, chain_name)
            try:
                cursor.execute(query, values)
                print(f'> Added RPC URL {entry["url"]}')
            except sqlite3.IntegrityError as e:
                if "UNIQUE constraint failed" in str(e):
                    unique_rpc_counter = unique_rpc_counter + 1
        if unique_rpc_counter > 0:
            print(f"{unique_rpc_counter} RPC URL:s already existing in the database were skipped")

    conn.commit()
    conn.close()


# # # EXPORT # # #

def export_data(args) -> None:
    print(f'Export target: directory {args.target}')
    if not Path(args.target).exists():
        print(f"> Target directory {args.target} does not exist, creating.")
        Path(args.target).mkdir(parents=True, exist_ok=True)
    if args.source_url:
        print(f'Export source: API at URL {args.source_url}')
        api_export_json(Path(args.target) / 'chains.json', args.source_url + '/all/chains', sort_by='name', force=args.force)
        api_export_json(Path(args.target) / 'rpc_urls.json', args.source_url + '/all/rpc_urls', sort_by='chain_name', force=args.force)
    if args.source_db:
        print(f'Export source: database on path {args.source_db}')
        local_export_to_json_files(Path(args.target) / 'chains.json', Path(args.target) / 'rpc_urls.json', args.source_db, force=args.force)


def api_export_json(path: Path, url: str, sort_by: str, force: bool) -> None:
    response = requests.get(url, timeout=5)
    if response.status_code == 200:
        data = response.json()
    else:
        print(response.text)
    sorted_data = sorted(data, key=lambda x: x[sort_by])
    if allow_overwrite(path, force):
        export_to_file(path, sorted_data)


def local_export_to_json_files(target_chains: Path, target_rpc_urls: Path, db_file: str, force: bool) -> None:
    """Exports data from an SQLite database into JSON files.
    The output JSON files has a specific format, see `db_json` folder in this repository.
    """
    conn = sqlite3.connect(db_file)
    conn.execute('PRAGMA foreign_keys = ON')
    cursor = conn.cursor()

    if target_chains:
        query_chains = f'SELECT name, api_class FROM {TABLE_CHAINS}'
        entries_chains = cursor.execute(query_chains).fetchall()
        local_export_chains(target_chains, entries_chains, force=force)

    if target_rpc_urls:
        query_rpc_urls = f'SELECT url, chain_name FROM {TABLE_RPC_URLS}'
        entries_rpc_urls = cursor.execute(query_rpc_urls).fetchall()
        local_export_rpc_urls(target_rpc_urls, entries_rpc_urls, force=force)

    conn.commit()
    conn.close()


def local_export_chains(target_chains: Path, entries: list, force: bool) -> None:
    data_chains = []
    for entry in entries:
        name = entry[0]
        api_class = entry[1]
        data_chains.append({'name': name, 'api_class': api_class})
    sorted_chains = sorted(data_chains, key=lambda x: x['name'])
    if allow_overwrite(target_chains, force):
        export_to_file(target_chains, sorted_chains)


def local_export_rpc_urls(target_rpc_urls: Path, entries: list, force: bool) -> None:
    data_rpc_urls = []
    for entry in entries:
        url = entry[0]
        chain_name = entry[1]
        data_rpc_urls.append({'url': url, 'chain_name': chain_name})
    sorted_urls = sorted(data_rpc_urls, key=lambda x: x['chain_name'])
    if allow_overwrite(target_rpc_urls, force):
        export_to_file(target_rpc_urls, sorted_urls)


# # # REQUEST # # #

def make_get_request(url: str) -> None:
    response = requests.get(url, timeout=5)
    if response.status_code == 200:
        data = response.json()
        for d in data:
            print(d)
    else:
        print(response.text)


def get_all_chains(args) -> None:
    make_get_request(args.url + '/all/chains')


def get_all_rpc_urls(args) -> None:
    make_get_request(args.url + '/all/rpc_urls')


def add_rpc(args) -> None:
    auth_header = get_auth_header(args.url, args.auth_pw)
    rpc = {'chain_name': args.chain, 'url': args.rpc}
    response = requests.post(args.url + '/create_rpc_url', json=rpc, headers=auth_header, timeout=5)
    print(response.text)


def delete_rpc(args) -> None:
    auth_header = get_auth_header(args.url, args.auth_pw)
    protocol = args.rpc.split('://')[0]
    address = args.rpc.split('://')[1]
    response = requests.delete(args.url + f'/delete_url?protocol={protocol}&address={address}', headers=auth_header, timeout=5)
    print(response.text)


def add_chain(args) -> None:
    auth_header = get_auth_header(args.url, args.auth_pw)
    chain = {'name': args.chain, 'api_class': args.api_class}
    response = requests.post(args.url + '/create_chain', json=chain, headers=auth_header, timeout=5)
    print(response.text)


def delete_chain(args) -> None:
    auth_header = get_auth_header(args.url, args.auth_pw)
    chain = args.chain
    response = requests.delete(args.url + f'/delete_chain?name={chain}', headers=auth_header, timeout=5)
    print(response.text)


# # # JSON # # #

def validate_json(args) -> None:
    path_chains = Path(args.directory) / 'chains.json'
    path_rpcs = Path(args.directory) / 'rpc_urls.json'
    if not path_chains.exists() or not path_rpcs.exists():
        raise FileNotFoundError(f"Cannot find required files {path_chains} and {path_rpcs}")

    chains = load_json_file(path_chains)
    rpcs = load_json_file(path_rpcs)
    if args.filter:
        chains = list(filter(lambda x: args.filter.lower() in x['name'].lower(), chains))
        rpcs = list(filter(lambda x: args.filter.lower() in x['chain_name'].lower(), rpcs))
    chain_names = [c['name'] for c in chains]
    if args.reverse:
        rpcs.reverse()
    error_log = []

    # TODO: make this a session of async tasks to shorten time to run
    for rpc in rpcs:
        print(f'Validating {rpc["url"]}')
        # Confirm chain exists for URLs
        if rpc['chain_name'] not in chain_names:
            print(f'#> Chain name error for {rpc["url"]}')
            error_log.append(f'Chain {rpc["chain_name"]} missing for URL {rpc["url"]}')
            continue

        # Confirm endpoints respond
        chain = [c for c in chains if c.get('name') == rpc['chain_name']][0]
        api_class = chain['api_class']
        headers = {'Content-Type': 'application/json'}
        payload = {
            "jsonrpc": "2.0",
            "method": get_jsonrpc_method(api_class),
            "params": [],
            "id": 1
        }
        if 'http' in rpc['url']:
            try:
                if api_class == 'aptos':
                    response = requests.get(rpc['url'], timeout=5)
                else:
                    response = requests.post(rpc['url'], json=payload, headers=headers, timeout=3)
                if not response.status_code == 200:
                    print(f'#> URL error for {rpc["url"]}')
                    error_log.append(f'URL {rpc["url"]} produced response.text={response.text} with status_code={response.status_code}')
            except Exception as e:
                error_log.append(f'URL {rpc["url"]} failed HTTP connection: {e}')
        elif 'ws' in rpc['url']:
            try:
                ws = websocket.create_connection(rpc['url'])
                ws.send(json.dumps(payload))
                response = json.loads(ws.recv())
                ws.close()
                if 'jsonrpc' not in response.keys():
                    print(f'#> error for {rpc["url"]}')
                    error_log.append(f'URL {rpc["url"]} produced WS response={response}')
            except Exception as e:
                error_log.append(f'URL {rpc["url"]} failed WS connection: {e}')

    if len(error_log) > 0:
        print('#> Error report <#')
        for e in error_log:
            print(e)


# # # UTILS # # #

# TODO: this doesn't really return a string, does it?
def get_auth_header(url: str, password: str = "") -> str:
    if not password:
        with open(PATH_DEFAULT_AUTH_PW, 'r', encoding='utf-8') as f:
            auth_pw = f.readline().strip()
    elif password:
        auth_pw = password
    else:
        raise ValueError("Missing authentication password for access token request!")
    token_response = requests.post(url + '/token', json={'username': 'dwellir_endpointdb', 'password': f'{auth_pw}'}, timeout=5)
    if token_response.status_code != 200:
        raise requests.exceptions.HTTPError(f'Couldn\'t get access token, {token_response.text}')
    return {'Authorization': f'Bearer {token_response.json()["access_token"]}'}


def get_jsonrpc_method(api_class: str) -> str:
    """Get the JSON-RPC method for the API class."""
    if api_class == 'substrate':
        return 'chain_getHeader'
    if api_class == 'ethereum':
        return 'eth_blockNumber'
    if api_class == 'starknet':
        return 'starknet_blockNumber'
    if api_class == "filecoin":
        return "Filecoin.ChainHead"
    if api_class == "sui":
        return "sui_getLatestCheckpointSequenceNumber"
    if api_class == "ton":
        return "getMasterchainInfo"
    else:
        raise ValueError('Invalid api_class:', api_class)


def load_json_file(filepath: Path):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            result = json.load(f)
    except FileNotFoundError as e:
        print(e)
        result = None
    return result


def export_to_file(file_name: Path, data: dict) -> None:
    with open(file_name, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def allow_overwrite(filepath: Path, force: bool) -> bool:
    if force:
        return True
    if filepath.exists():
        user_input = input(f"File {filepath} already exists, overwrite? (y/n): ")
        if user_input.lower() not in ['y', 'yes']:
            return False
    return True


if __name__ == '__main__':
    main()
