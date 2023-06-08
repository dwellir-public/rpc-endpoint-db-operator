#!/usr/bin/env python3

import requests
import json
import argparse
import sqlite3
from pathlib import Path


DEFAULT_URL = 'http://localhost:5000'
DEFAULT_FILE = Path.cwd() / 'live_database.db'

TABLE_CHAINS = 'chains'
TABLE_RPC_URLS = 'rpc_urls'


# TODO: define json schemas for database entries


def main() -> None:
    parser = argparse.ArgumentParser(description='Import or export JSON data to or from the chain database')
    parser.add_argument('--api',  action='store_true', help='If the script should operate with the database API endpoint')
    parser.add_argument('--url', type=str, help='The url for the API of the database', default=DEFAULT_URL)
    parser.add_argument('--auth_password', type=str, help='The password needed to get an access token from the Flask app', default="")
    parser.add_argument('--local', action='store_true',  help='If the script should operate with a local database file')
    parser.add_argument('--db_file', type=str, help='The local database file', default=DEFAULT_FILE)

    # TODO: make --local and --api implicit based on existance of db_file/url

    parser.add_argument('-i', '--import_data', action='store_true',
                        help='Import data to the database from the target JSON file. Overwrites existing entries for matching identifiers.')
    parser.add_argument('-e', '--export_data', action='store_true',
                        help='Export data from the database to the target JSON file. Note: will overwrite the target JSON files!')
    parser.add_argument('--json_chains', type=str, help='The JSON file target for "chains"')
    parser.add_argument('--json_rpc_urls', type=str, help='The JSON file target for "rpc_urls"')
    args = parser.parse_args()

    if args.api and args.local:
        raise ValueError('Cannot specify both "api" and "local"')
    if not any([args.api, args.local]):
        raise ValueError('Specify either "api" or "local"')
    if args.import_data and args.export_data:
        raise ValueError('Cannot specify both "import_data" and "export_data"')
    if not any([args.import_data, args.export_data]):
        raise ValueError('Specify either "import_data" or "export_data"')
    if not any([args.json_chains, args.json_rpc_urls]):
        print('No JSON files supplied, exiting.')
        return

    path_db_file = Path.cwd() / args.db_file
    path_chains = Path.cwd() / args.json_chains if args.json_chains else None
    path_urls = Path.cwd() / args.json_rpc_urls if args.json_rpc_urls else None

    # TODO: add user-check in cased of file overwrite

    if args.local and not path_db_file.exists():
        raise FileNotFoundError(f'Database file {args.file} not found')

    if args.api:
        if args.import_data:
            api_import_from_json_files(path_chains, path_urls, args.url, args.auth_password)
        if args.export_data:
            api_export_to_json_files(path_chains, path_urls, args.url)

    if args.local:
        if args.import_data:
            local_import_from_json_files(path_chains, path_urls, path_db_file)
        if args.export_data:
            local_export_to_json_files(path_chains, path_urls, path_db_file)

def export_to_file(file_name: Path, data: dict):
    """
    Writes data to a file.
    """
    with open(file_name, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
        print(f'exported data to {file_name}')

def api_export_json(path: Path, url: str):
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
    else:
        print(response.text)
    # check if path exists
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        export_to_file(path, data)
    elif path.exists():
        user_input = input("File already exists for json chain, overwrite? (y/n): ")
        if user_input in ['y', 'Y', 'yes', 'Yes', 'YES']:
            export_to_file(path, data)
        else:
            print('exiting, no data exported')


def api_export_to_json_files(json_chains: Path, json_rpc_urls: Path, api_url: str):
    """
    Exports data from the SQLite database to JSON files.
    Assumes the JSON files has a specific format as defined by XYZ.
    """
    api_export_json(json_chains, api_url + '/all/chains')
    api_export_json(json_rpc_urls, api_url + '/all/rpc_urls')

def api_import_from_json_files(json_chains: Path, json_rpc_urls: Path, api_url: str, auth_pw: str = ""):
    """
    Imports data from JSON files into an SQLite database.
    Assumes the JSON files has a specific format as defined by XYZ. # TODO: mention the schema when implemented
    """
    token_response = requests.post(api_url + '/token', json={'username': 'dwellir_endpointdb', 'password': f'{auth_pw}'}, timeout=5)
    if token_response.status_code != 200:
        raise requests.exceptions.HTTPError(f'Couldn\'t get access token, {token_response.text}')
    authorization_header = {'Authorization': f'Bearer {token_response.json()["access_token"]}'}

    if json_chains:
        print(f'> importing chain data from {json_chains.name}')
        with open(json_chains, 'r', encoding='utf-8') as f:
            data_chains = json.load(f)
            url_format = api_url + '/create_chain'
        for chain in data_chains:
            print(chain)
            response = requests.post(url_format, json=chain, headers=authorization_header, timeout=5)
            if response.status_code == 201:
                print(f'added chain {chain["name"]}')
            else:
                print(response.text)

    if json_rpc_urls:
        print(f'> importing url data from {json_rpc_urls.name}')
        with open(json_rpc_urls, 'r', encoding='utf-8') as f:
            data_rpc_urls = json.load(f)
            url_format = api_url + '/create_rpc_url'
        for rpc_url in data_rpc_urls:
            response = requests.post(url_format, json=rpc_url, headers=authorization_header, timeout=5)
            if response.status_code == 201:
                print(f'added rpc url {rpc_url["url"]}')
            else:
                print(response.text)

    print(f'> data written to database on url: {api_url}')


def local_import_from_json_files(json_chains: Path, json_rpc_urls: Path, db_file: Path):
    """
    Imports data from JSON files into an SQLite database.
    Assumes the JSON files has a specific format as defined by XYZ. # TODO: mention the schema when implemented
    """
    conn = sqlite3.connect(db_file)
    conn.execute('PRAGMA foreign_keys = ON')
    cursor = conn.cursor()

    if json_chains:
        print(f'> importing chain data from {json_chains.name}')
        with open(json_chains, 'r', encoding='utf-8') as f:
            data_chains = json.load(f)
        for entry in data_chains:
            name = entry['name']
            api_class = entry['api_class']
            query = f'INSERT INTO {TABLE_CHAINS} (name, api_class) VALUES (?, ?)'
            values = (name, api_class)
            try:
                cursor.execute(query, values)
            except sqlite3.IntegrityError as e:
                # TODO: implement graceful way of "insert only if not exists" and then re-enable this
                # conn.rollback()
                print(f'Database error for {{{name}, {api_class}}}:', e)

    if json_rpc_urls:
        print(f'> importing url data from {json_rpc_urls.name}')
        with open(json_rpc_urls, 'r', encoding='utf-8') as f:
            data_rpc_urls = json.load(f)
        for entry in data_rpc_urls:
            url = entry['url']
            chain_name = entry['chain_name']
            query = f'INSERT INTO {TABLE_RPC_URLS} (url, chain_name) VALUES (?, ?)'
            values = (url, chain_name)
            try:
                cursor.execute(query, values)
            except sqlite3.IntegrityError as e:
                # conn.rollback()
                print(f'Database error for {{{url}, {chain_name}}}:', e)

    conn.commit()
    conn.close()
    print(f'> data written to database file {db_file.name}')


def local_export_to_json_files(json_chains: Path, json_rpc_urls: Path, db_file: Path):
    """
    Exports data from an SQLite database into JSON files.
    The output JSON files has a specific format as defined by XYZ. # TODO: mention the schema when implemented
    """
    print(f'> exporting data from {db_file.name}')
    conn = sqlite3.connect(db_file)
    conn.execute('PRAGMA foreign_keys = ON')
    cursor = conn.cursor()

    if json_chains:
        query_chains = f'SELECT name, api_class FROM {TABLE_CHAINS}'
        entries_chains = cursor.execute(query_chains).fetchall()
        data_chains = []
        for entry in entries_chains:
            name = entry[0]
            api_class = entry[1]
            data_chains.append({'name': name, 'api_class': api_class})
        sorted_chains = sorted(data_chains, key=lambda x: x['name'])
        with open(json_chains, 'w', encoding='utf-8') as f:
            json.dump(sorted_chains, f, ensure_ascii=False, indent=4)
        print(f'> data written to {json_chains.name}')

    if json_rpc_urls:
        query_rpc_urls = f'SELECT url, chain_name FROM {TABLE_RPC_URLS}'
        entries_rpc_urls = cursor.execute(query_rpc_urls).fetchall()
        data_rpc_urls = []
        for entry in entries_rpc_urls:
            url = entry[0]
            chain_name = entry[1]
            data_rpc_urls.append({'url': url, 'chain_name': chain_name})
        sorted_urls = sorted(data_rpc_urls, key=lambda x: x['chain_name'])
        with open(json_rpc_urls, 'w', encoding='utf-8') as f:
            json.dump(sorted_urls, f, ensure_ascii=False, indent=4)
        print(f'> data written to {json_rpc_urls.name}')


if __name__ == '__main__':
    main()
