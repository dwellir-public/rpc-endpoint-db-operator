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
    parser.add_argument('--local', action='store_true',  help='If the script should operate with a local database file')
    parser.add_argument('--db_file', type=str, help='The local database file', default=DEFAULT_FILE)

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

    if args.local and not path_db_file.exists():
        raise FileNotFoundError(f'Database file {args.file} not found')

    if args.api:
        print('using api database')
        if args.json_chains and args.json_rpc_urls:
            raise ValueError('Cannot specify both "json_chains" and "json_rpc_urls"')
        if args.json_chains:
            with open(path_chains, 'r', encoding='utf-8') as f:
                data_chains = json.load(f)
                for chain in data_chains:
                    response = requests.post(args.url, json=chain)
                # print(response.status_code, response.text)
                    if response.status_code == 201:
                        print(f'added chain {chain["name"]}')
                    else:
                        print(response.text)
        if args.json_rpc_urls:
            with open(path_urls, 'r', encoding='utf-8') as f:
                data_urls = json.load(f)
                for url in data_urls:
                    response = requests.post(args.url, json=url)
                    if response.status_code == 201:
                        print(f'added rpc url {url["url"]}')
                    else:
                        print(response.text)

    if args.local:
        if args.import_data:
            # TODO: fix
            print(
                f'> importing data from {path_chains.name if path_chains else "_"} and {path_urls.name if path_urls else "_"}')
            import_from_json_files(path_chains, path_urls, path_db_file)
            print(f'> data written to database file {path_db_file.name}')
        if args.export_data:
            print(f'> exporting data from {path_db_file.name}')
            export_to_json_files(path_chains, path_urls, path_db_file)
            print(f'> data written to {path_chains.name if path_chains else "_"} and {path_urls.name if path_urls else "_"}')


def import_from_json_files(json_chains: Path, json_rpc_urls: Path, db_file: Path):
    """
    Imports data from two JSON file into an SQLite database.
    Assumes the JSON files has a specific format as defined by XYZ. # TODO: mention the schema when implemented
    """
    conn = sqlite3.connect(db_file)
    conn.execute('PRAGMA foreign_keys = ON')
    cursor = conn.cursor()

    if json_chains:
        with open(json_chains, 'r', encoding='utf-8') as f:
            data_chains = json.load(f)
        for entry in data_chains:
            name = entry['name']
            api_class = entry['api_class']
            query = f'INSERT INTO {TABLE_CHAINS} (name, api_class) VALUES (?, ?)'
            values = (name, api_class)
            cursor.execute(query, values)

    if json_rpc_urls:
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
                conn.rollback()
                print(f'Database error for {{{url}, {chain_name}}}:', e)

    conn.commit()
    conn.close()


def export_to_json_files(json_chains: Path, json_rpc_urls: Path, db_file: Path):
    """
    Exports data from an SQLite database into two JSON files.
    The output JSON files has a specific format as defined by XYZ. # TODO: mention the schema when implemented
    """
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
        with open(json_chains, 'w', encoding='utf-8') as f:
            json.dump(data_chains, f, ensure_ascii=False, indent=4)

    if json_rpc_urls:
        query_rpc_urls = f'SELECT url, chain_name FROM {TABLE_RPC_URLS}'
        entries_rpc_urls = cursor.execute(query_rpc_urls).fetchall()
        data_rpc_urls = []
        for entry in entries_rpc_urls:
            url = entry[0]
            chain_name = entry[1]
            data_rpc_urls.append({'url': url, 'chain_name': chain_name})
        with open(json_rpc_urls, 'w', encoding='utf-8') as f:
            json.dump(data_rpc_urls, f, ensure_ascii=False, indent=4)


if __name__ == '__main__':
    main()
