#!/usr/bin/env python3

"""Application to manage a database of blockchain endpoints."""

import logging
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, Response, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required

TABLE_CHAINS = "chains"
TABLE_RPC_URLS = "rpc_urls"
PATH_DIR = Path(__file__).resolve().parent
PATH_DB = PATH_DIR / "live_database.db"
PATH_JWT_SECRET_KEY = PATH_DIR / "auth_jwt_secret_key"
PATH_PASSWORD = PATH_DIR / "auth_password"

logging.basicConfig(level=logging.INFO)

# Confirm authorization file availability
if not PATH_PASSWORD.exists():
    raise FileNotFoundError(f"Password file not found on {str(PATH_PASSWORD)}, check the README.md for a setup guide")
if not PATH_JWT_SECRET_KEY.exists():
    raise FileNotFoundError(
        f"JWT secret key file not found on {str(PATH_JWT_SECRET_KEY)}, check the README.md for a setup guide"
    )


# FLASK APP SETUP

app = Flask(__name__)
app.config["DATABASE"] = str(PATH_DB)
with PATH_JWT_SECRET_KEY.open() as jwt_file:
    JWT_SECRET_KEY = jwt_file.read().strip()
app.config["JWT_SECRET_KEY"] = JWT_SECRET_KEY
jwt = JWTManager(app)


# DATABASE SETUP

app.logger.info("CREATING database and tables %s", app.config["DATABASE"])
conn = sqlite3.connect(app.config["DATABASE"])
cursor = conn.cursor()
cursor.execute("""CREATE TABLE IF NOT EXISTS chains
                    (name TEXT PRIMARY KEY UNIQUE COLLATE NOCASE NOT NULL,
                    api_class TEXT COLLATE NOCASE NOT NULL)""")
cursor.execute("""CREATE TABLE IF NOT EXISTS rpc_urls
                    (url TEXT PRIMARY KEY UNIQUE COLLATE NOCASE NOT NULL,
                    chain_name TEXT COLLATE NOCASE NOT NULL,
                    FOREIGN KEY(chain_name) REFERENCES chains(name))""")
conn.commit()
conn.close()


# API ROUTES


@app.route("/token", methods=["POST"])
def generate_token():
    """Generate an access token.

    The token is needed to make requests to any protected (@jwt_required decorator)
    functions in this API. The password is stored securely on the machine of the app.
    Requires JSON data with parameters 'username' and 'password' in the request, example:

    curl -X POST http://localhost:5000/token -H 'Content-Type: application/json' \
        -d '{"username": "dwellir_endpointdb", "password": <password>}'
    """
    username = request.json.get("username", None)
    password = request.json.get("password", None)

    with PATH_PASSWORD.open() as pw_file:
        auth_password = pw_file.read().strip()
    if username != "dwellir_endpointdb" or password != auth_password:
        return jsonify({"msg": "Bad username or password"}), 401

    access_token = create_access_token(identity=username)
    return jsonify(access_token=access_token)


def insert_into_database(table: str, request_data: dict) -> Response:
    """Insert a record into the database table."""
    try:
        conn = sqlite3.connect(app.config["DATABASE"])
        conn.execute("PRAGMA foreign_keys = ON")  # enforce that any URL has an existing chain
        cursor = conn.cursor()
        columns = ", ".join(request_data.keys())
        placeholders = ":" + ", :".join(request_data.keys())
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        cursor.execute(query, request_data)
        conn.commit()
        conn.close()
        return jsonify({"message": "Record created successfully"}), 201
    except sqlite3.IntegrityError as e:
        conn.rollback()  # Roll back the transaction
        conn.close()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/create_chain", methods=["POST"])
@jwt_required()
def create_chain_record() -> Response:
    """Create a record in the 'chains' table, corresponding to the input data.

    Requires JSON data with parameters 'name' and 'api_class' in the request, example:

    curl -X POST http://localhost:5000/create_chain -d '{"name": "chain1", "api_class": "substrate"}' \
        -H 'Content-Type: application/json'
    """
    data = request.get_json()
    app.logger.debug("creating chains record from data: %s", data)
    if not all(key in data for key in ("name", "api_class")):
        return jsonify({"error": "Both name and api_class entries are required"}), 400
    values = {"name": data["name"], "api_class": data["api_class"]}
    if not is_valid_api(values["api_class"]):
        return jsonify({"error": {"error": "Invalid api"}}), 500
    return insert_into_database(TABLE_CHAINS, values)


# TODO: add endpoint to create multiple URL entries with one request?
@app.route("/create_rpc_url", methods=["POST"])
@jwt_required()
def create_rpc_url_record() -> Response:
    """Create a record in the 'rpc_urls' table, corresponding to the input data.

    Requires JSON data with parameters 'url' and 'chain_name' in the request, example:

    curl -X POST http://localhost:5000/create_rpc_url -d '{"url": "http://chain2.com", "chain_name": "chain2"}' \
        -H 'Content-Type: application/json'
    """
    data = request.get_json()
    app.logger.debug("creating rpc_urls record from data: %s", data)
    if not all(key in data for key in ("url", "chain_name")):
        return jsonify({"error": "Both url and chain_name entries are required"}), 400
    values = {"url": data["url"], "chain_name": data["chain_name"]}
    if not is_valid_url(values["url"]):
        return jsonify({"error": {"error": "Invalid url."}}), 500
    return insert_into_database(TABLE_RPC_URLS, values)


@app.route("/all/<string:table>", methods=["GET"])
def get_all_records(table: str) -> Response:
    """Get all the entries of the table in the path.

    curl 'http://localhost:5000/all/chains'
    """
    if table not in [TABLE_CHAINS, TABLE_RPC_URLS]:
        return jsonify({"error": f"unknown table {table}"}), 400
    conn = sqlite3.connect(app.config["DATABASE"])
    cursor = conn.cursor()

    if table == TABLE_CHAINS:
        cursor.execute(f"SELECT name, api_class FROM {TABLE_CHAINS}")
    if table == TABLE_RPC_URLS:
        cursor.execute(f"SELECT url, chain_name FROM {TABLE_RPC_URLS}")

    records = cursor.fetchall()
    conn.close()
    results = []

    if table == TABLE_CHAINS:
        for record in records:
            results.append({"name": record[0], "api_class": record[1]})
    if table == TABLE_RPC_URLS:
        for record in records:
            results.append({"url": record[0], "chain_name": record[1]})
    return jsonify(results)


@app.route("/get_chain_by_name/<string:name>", methods=["GET"])
def get_chain_by_name(name: str) -> Response:
    """Get the chain entry corresponding to the input chain name.

    curl 'http://localhost:5000/get_chain_by_name/PulseChain%20mainnet'
    """
    conn = sqlite3.connect(app.config["DATABASE"])
    cursor = conn.cursor()
    cursor.execute(f"SELECT name, api_class FROM {TABLE_CHAINS} WHERE name=?", (name,))
    record = cursor.fetchone()
    conn.close()
    if record:
        return jsonify({"name": record[0], "api_class": record[1]})
    return jsonify({"error": "Record not found"}), 404


@app.route("/get_chain_by_url", methods=["GET"])
def get_chain_by_url() -> Response:
    """Get the chain entry corresponding to the input url.

    Requires that url parameters 'protocol' and 'address' are present in the request, example:

    curl 'http://localhost:5000/get_chain_by_url?protocol=http&address=chain5.com'
    """
    try:
        url = url_from_request_args()
    except TypeError as e:
        app.logger.error("TypeError when trying to build RPC url from parameters: %s", str(e))
        return jsonify({"error": "url parameters 'protocol' and 'address' required for get_chain_by_url request"}), 400

    conn = sqlite3.connect(app.config["DATABASE"])
    cursor = conn.cursor()
    cursor.execute(f"SELECT url, chain_name FROM {TABLE_RPC_URLS} WHERE url=?", (url,))
    url_record = cursor.fetchone()
    if url_record:
        cursor.execute(f"SELECT name, api_class FROM {TABLE_CHAINS} WHERE name = ?", (url_record[1],))
        chain_record = cursor.fetchone()
        if chain_record:
            return jsonify({"name": chain_record[0], "api_class": chain_record[1]})
    conn.close()
    return jsonify({"error": "Record not found"}), 404


@app.route("/get_url", methods=["GET"])
def get_url() -> Response:
    """Get the RPC url entry corresponding to the input url.

    Requires that url parameters 'protocol' and 'address' are present in the request, example:

    curl -X GET 'http://localhost:5000/get_url?protocol=http&address=chain4.com'
    """
    try:
        url = url_from_request_args()
    except TypeError as e:
        app.logger.error("TypeError when trying to build RPC url from parameters: %s", str(e))
        return jsonify({"error": "url parameters 'protocol' and 'address' required for update_url_record request"}), 400

    conn = sqlite3.connect(app.config["DATABASE"])
    cursor = conn.cursor()
    cursor.execute(f"SELECT url, chain_name FROM {TABLE_RPC_URLS} WHERE url=?", (url,))
    record = cursor.fetchone()
    conn.close()
    if record:
        return jsonify({"url": record[0], "chain_name": record[1]})
    return jsonify({"error": "Record not found"}), 404


# Get urls for a specific chain
@app.route("/get_urls/<string:chain_name>", methods=["GET"])
def get_urls(chain_name: str) -> Response:
    """Get the RPC URL entries corresponding to the chain name in the path.

    curl -X GET 'http://localhost:5000/get_urls/chain5'
    """
    conn = sqlite3.connect(app.config["DATABASE"])
    cursor = conn.cursor()
    cursor.execute(f"SELECT url, chain_name FROM {TABLE_RPC_URLS} WHERE chain_name=?", (chain_name,))
    records = cursor.fetchall()
    conn.close()
    urls = []
    for record in records:
        urls.append(record[0])
    if len(urls) > 0:
        return jsonify(urls)
    return jsonify({"error": f"No urls found for chain {chain_name}"}), 404


@app.route("/update_url", methods=["PUT"])
@jwt_required()
def update_url_record() -> Response:
    """Update the rpc_urls entry corresponding to the input url.

    Requires that url parameters 'protocol' and 'address' are present in the request, example:

    curl -X PUT -H 'Content-Type: application/json' -d '{"url": "http://chain6.com", "chain_name": "chain6"}' \
        'http://localhost:5000/update_url?protocol=http&address=chain4.com'
    """
    try:
        url_old = url_from_request_args()
    except TypeError as e:
        app.logger.error("TypeError when trying to build RPC url from parameters: %s", str(e))
        return jsonify({"error": "url parameters 'protocol' and 'address' required for update_url_record request"}), 400

    try:
        url_new = request.json["url"]
        chain_name = request.json["chain_name"]
    except KeyError as e:
        return jsonify({"error": f"Missing required parameters, {e}"}), 400
    if not is_valid_url(url_new):
        return jsonify({"error": "Invalid url"}), 500

    conn = sqlite3.connect(app.config["DATABASE"])
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"UPDATE {TABLE_RPC_URLS} SET url=?, chain_name=? WHERE url=?",
            (url_new, chain_name, url_old),
        )
    except sqlite3.IntegrityError as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    conn.commit()
    conn.close()
    if cursor.rowcount == 0:
        rval = jsonify({"error": "No such record"})
    else:
        rval = jsonify({"url": url_new, "chain_name": chain_name})
    return rval


@app.route("/delete_chain", methods=["DELETE"])
@jwt_required()
def delete_chain_record() -> Response:
    """Delete the chain entry corresponding to the input name.

    Requires that url parameter 'name' is present in the request, example:

    curl -X DELETE 'http://localhost:5000/delete_chain?name=chain5'
    """
    name = request.args.get("name")
    conn = sqlite3.connect(app.config["DATABASE"])
    cursor = conn.cursor()
    try:
        cursor.execute(f"DELETE FROM {TABLE_CHAINS} WHERE name=?", (name,))
        # TODO: should urls referencing this chains entry also be deleted at this point? since their foreign key now is missing
    except sqlite3.IntegrityError as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": str(e)}), 400
    conn.commit()
    conn.close()
    if cursor.rowcount == 0:
        rval = jsonify({"error": f"Record with name '{name}' not found"})
    else:
        rval = jsonify({"message": "Chain record deleted successfully"})
    return rval


@app.route("/delete_url", methods=["DELETE"])
@jwt_required()
def delete_url_record() -> Response:
    """Delete the rpc_urls entry corresponding to the input url.

    Requires that url parameters 'protocol' and 'address' are present in the request, example:

    curl -X DELETE 'http://localhost:5000/delete_url?protocol=http&address=chain5.com'
    """
    try:
        url = url_from_request_args()
    except TypeError as e:
        app.logger.error("TypeError when trying to build RPC url from parameters: %s", str(e))
        return jsonify({"error": "url parameters 'protocol' and 'address' required for delete_url request"}), 400

    conn = sqlite3.connect(app.config["DATABASE"])
    cursor = conn.cursor()
    try:
        cursor.execute(f"DELETE FROM {TABLE_RPC_URLS} WHERE url=?", (url,))
    except sqlite3.IntegrityError as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": str(e)}), 400
    conn.commit()
    conn.close()
    if cursor.rowcount == 0:
        rval = jsonify({"error": f"Record with url '{url}' not found"})
    else:
        rval = jsonify({"message": "RPC url record deleted successfully"})
    return rval


@app.route("/delete_urls", methods=["DELETE"])
@jwt_required()
def delete_url_records() -> Response:
    """Delete the url entries corresponding to the input chain_name.

    Requires that url parameter 'chain_name' is present in the request, example:

    curl -X DELETE 'http://localhost:5000/delete_urls?chain_name=chain3'
    """
    chain_name = request.args.get("chain_name")
    conn = sqlite3.connect(app.config["DATABASE"])
    cursor = conn.cursor()
    try:
        cursor.execute(f"DELETE FROM {TABLE_RPC_URLS} WHERE chain_name=?", (chain_name,))
    except sqlite3.IntegrityError as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": str(e)}), 400
    conn.commit()
    conn.close()
    if cursor.rowcount == 0:
        rval = jsonify({"error": f"Records with chain_name '{chain_name}' not found"})
    else:
        rval = jsonify({"message": "RPC url records deleted successfully"})
    return rval


@app.route("/chain_info", methods=["GET"])
def get_chain_info():
    """Get info for the chain corresponding to the input name.

    Requires that url parameter 'name' is present in the request, example:

    curl "http://localhost:5000/chain_info?name=chain2"
    """
    # Get parameters from the request URL
    chain_name = request.args.get("chain_name")
    if not chain_name:
        return jsonify({"error": "Missing required parameter 'chain_name'"}), 400
    conn = sqlite3.connect(app.config["DATABASE"])
    cursor = conn.cursor()
    # Fetch chain
    cursor.execute(f"SELECT * FROM {TABLE_CHAINS} WHERE name=?", (chain_name,))
    chain_record = cursor.fetchone()
    if not chain_record:
        return jsonify({"error": f"Chain '{chain_name}' not found in database"}), 404
    # Fetch urls
    cursor.execute(f"SELECT url, chain_name FROM {TABLE_RPC_URLS} WHERE chain_name=?", (chain_name,))
    url_records = cursor.fetchall()
    conn.close()
    urls = []
    for ur in url_records:
        urls.append(ur[0])
    result = {"chain_name": chain_record[0], "api_class": chain_record[1], "urls": urls}
    # Return the chain info as JSON
    return jsonify(result), 200


# UTILITY FUNCTIONS

VALID_API_CLASSES = [
    "substrate",
    "ethereum",
    "starknet",
    "filecoin",
    "sui",
    "waves",
    "ton",
    "tonv3",
    "sidecar",
    "cosmos-tendermint",
    "eos",
    "eth-v1-beacon",
    "tron",
    "movement",
]


def is_valid_api(api: str) -> bool:
    """Test that an API class string is valid."""
    return api.lower() in VALID_API_CLASSES


def is_valid_url(url: str) -> bool:
    """Test that a url is valid, e.g. only http(s) and ws(s)."""
    allowed_schemes = {"http", "https", "ws", "wss"}
    try:
        result = urlparse(url)
        return all([result.scheme in allowed_schemes, result.netloc])
    except ValueError:
        return False


def url_from_request_args() -> str:
    """Return a full url from url parameters 'protocol' and 'address'.

    Caller is responsible for excepting any errors.
    """
    protocol = request.args.get("protocol")
    address = request.args.get("address")
    return protocol + "://" + address


# MAIN

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0")
