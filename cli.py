#!/bin/env python3
import argparse
import re
import requests
import json

# Custom action to parse a list of URLs:
class ListAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        url_list = values.split(',')
        for url in url_list:
            if not url_regex.match(url):
                raise argparse.ArgumentTypeError(f"Invalid URL: {url}")
        setattr(namespace, self.dest, url_list)

BASE_URL = "http://localhost:5000"

parser = argparse.ArgumentParser(description="API command-line interface")
parser.add_argument("action", choices=["add", "remove", "update", "lookup", "dump"], help="Action to perform")
parser.add_argument("-i", "--id", nargs="?", type=int, help="ID of the record")
parser.add_argument("-c", "--chain_id", type=int, help="Numeric id for a chain")
parser.add_argument("-n", "--name", help="Name of the chain")
parser.add_argument("-u", "--urls", nargs="?", action=ListAction, help="List of URLs separated by comma. (-u 'http://abc.se,wss://cde.se')")
url_regex = re.compile(r'^(?:http|ftp|ws|wss)s?://'  # http:// or https:// or ftp:// or ftps:// or ws:// or wss://
                                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
                                r'localhost|'  # localhost...
                                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or IP
                                r'(?::\d+)?'  # optional port
                                r'(?:/?|[/?]\S+)$', re.IGNORECASE)

args = parser.parse_args()

if args.action == "add":
    if args.id is not None:
        print('id is not a possible argument for add.')
        exit(1)
    if not args.name or not args.urls:
        print('Missing required parameters name or urls')
        exit(1)
    if not isinstance(args.chain_id, int):
        print(f"chain_id {args.chain_id} must be an integer")
        exit(1)
    if not isinstance(args.name, str):
        print('Chain name must be a string')
        exit(1)
    if not isinstance(args.urls, list):
        print('URLs must be a list')
        exit(1)

    for url in args.urls:
        if not re.match(url_regex, url):
            print(f'{url} is not a valid URL')
            exit(1)
    
    data = {'chain_id': args.chain_id, 'chain_name': args.name, 'urls': args.urls}
    response = requests.post(BASE_URL + "/create", json=data)
    print(response.json())

elif args.action == "remove":
    if args.id is None:
        print("Error: ID is required for removing a record.")
        exit(1)
    response = requests.delete(BASE_URL + "/delete/{}".format(args.id))
    print(response.json())

elif args.action == "update":
    if args.id is None:
        print("Error: ID is required for updating a record.")
        exit(1)
    data = {}
    if args.chain_id:
        data["chain_id"] = args.chain_id
    if args.name:
        data["chain_name"] = args.name
    if args.urls:
        for url in args.urls:
            data["urls"] = args.urls

    response = requests.put(BASE_URL + "/update/{}".format(args.id), json=data)
    print(response.json())

elif args.action == "lookup":
    if args.id is None:
        print("Error: ID is required for looking up a record.")
        exit(1)
    response = requests.get(BASE_URL + "/get/{}".format(args.id))
    print(response.json())

elif args.action == "dump":
    """ Dump the database in json."""
    response = requests.get(BASE_URL + "/all")
    response_json = response.json()
    print(json.dumps(response_json, indent=2))