# endpointdb

This repo holds tools to maintain a database of public RPC endpoints for blockchains. A good source to find new endpoints is [chainlist.org](https://chainlist.org/).

It also holds a tool to update an InfluxDB database with latency and block height information.

## Setup

### Prepare the environment

Fetch the `endpointdb` repo to your target environment. If not already configured, you will need to create a new SSH key to add as a deploy key for the repo.

    # If a new key is needed
    ssh-keygen -t ed25519
    # Add ~/.ssh/id_ed25519.pub to 'Deploy keys' in the endpointdb repo on GitHub
    git clone git@github.com:dwellir-public/endpointdb.git

Install `influxdb2` and Python tools by running the `install-dependencies.sh` script in your target environment. 

    cd endpointdb
    ./install-dependencies.sh

Create a new virtual environment in the repo and install the Python requirements.

    # cwd should be the endpointdb repo root directory
    python3 -m venv venv
    source venv/bin/activate
    pip3 install -r requirements.txt


### Set up InfluxDB

Enable `influxdb`.

    sudo systemctl enable influxdb --now

Set up `influx`. You will be prompted to configure the primary user and can answer as shown in the example below. For a production deployment, remember to store the selected login information in the keepass.

    sudo influx setup
    > Welcome to InfluxDB 2.0!
    ? Please type your primary username admin
    ? Please type your password ********
    ? Please type your password again ********
    ? Please type your primary organization name dwellir
    ? Please type your primary bucket name default
    ? Please type your retention period in hours, or 0 for infinite (0) 720

Create an InfluxDB token that can read and write to all buckets (this level of access might be overkill, evaluate what's needed in production deployment). Be sure to store the token value in keepass for production deployments.

    sudo influx auth create --write-buckets --read-buckets

Create a bucket for the block height data.

    sudo influx bucket create -n block_heights -r 30d

### Set up authentication

To make sure we can safely open up a public port for access to the database via the Flask API we need to add a layer of authentication. This is handled through a JWT which is generated by the `app.py` based on a secret and a username. The secret should be unique for each site and is generated like this:

    # cwd should be the endpointdb repo root directory
    openssl rand -hex 32 > auth_jwt_secret_key

The key should be stored in the `endpointdb` repo in the container of the deployment, where the app is hard-coded to look for it in the `auth_jwt_secret_key` file. We're also using the same setup for the password required to generate the token through an API request:

    # cwd should be the endpointdb repo root directory
    openssl rand -hex 32 > auth_password

With these two in place and accessible by the Flask app, we'll be able to generate an access token through the `/token` endpoint.

## Usage

### Start and initialize the blockchain RPC database

The API endpoint database is an SQLite database which is interfaced and used via a Flask API.

Start the database, preferrably using a `screen`. Exit the screen gracefully with Ctrl + A + D.

    screen -S endpointdb-app
    # The screen opens a new shell, so we'll have to re-activate the virtual environment
    > source venv/bin/activate
    > python3 app.py

Populate the database with initial information. The `json` directory in the repo contains `.json` files with backed up blockchain RPC urls that you can initialize from, if you haven't got access to a better source, though the list might not be 100 % up to date.

    python3 db_util.py --import_data --local --db_file live_database.db --json_chains db_json/chains.json --json_rpc_urls db_json/rpc_urls.json

### Start the influx updater

To start pushing data to the block height database, we run the `update_influxdb.py` script. It can be run from the same machine as the database was initialized on but could also be run from an entirely different machine. The script uses the information from a config file, `config.json` by default, to find the Flask API and the Influx database, as well as accessing them.

    screen -S update-influxdb  # optional
    python3 ./update_influxdb.py

### Query the blockchain RPC database via the Flask API

The Flask API supportes all of CRUD: "Create, Read, Update, Delete". Here follows some `curl` examples:

Create a chain record

    curl -X POST -H "Content-Type: application/json" -d \
    '{
        "name": "TESTCHAIN",
        "api_class": "substrate"
    }' \
    http://localhost:5000/create_chain

Create a URL record

    curl -X POST -H 'Content-Type: application/json' -d \
    '{
        "url": "https://foo.bar",
        "chain_name": "TESTCHAIN"
    }' \
    http://localhost:5000/create_rpc_url

Get the URL record

    curl -X GET -H 'http://localhost:5000/get_url?protocol=https&address=foo.bar'

Update the URL record

    curl -X PUT -H 'Content-Type: application/json' -d \
    '{
        "url": "https://foofoo.bar",
        "chain_name": "chain6"
    }' \
    http://localhost:5000/update_url?protocol=https&address=foo.bar

Delete a URL record

    curl -X DELETE http://localhost:5000/delete_url/?protocol=https&address=foofoo.bar

Get all records

    curl http://localhost:5000/all/chains
    curl http://localhost:5000/all/rpc_urls

Get an access token (`username` is hardcoded and `password` is manually generated on the app's machine)

    curl -X POST -d '{"username": "dwellir_endpointdb", "password": <password>}' -H 'Content-Type: application/json' http://localhost:5000/token

Use access token in query

    curl -H 'Authorization: Bearer <token>' http://localhost:5000/protected-endpoint

### Query the InfluxDB via the command line

TODO!

## Grafana

An intention of this application is to gain a good monitoring overview through Grafana.

### Adding the datasource

- Enter the Grafana web GUI.
- Go to the 'Add datasource' section.
- Select InfluxDB as the datasource type.
- Set Flux as the query language.
- Set the host IP and port (default port is 8086).
- Add the InfluxDB details; organizaiton, token (the one generated when setting up the database) and data bucket.

![Example image](grafana-datasource-setup.png?raw=true "Example image")

### Running an influx query in grafana

You can use this example query in grafana, under the 'Explore section'. Simply paste the code below and press "Run query". If both the `app.py` and `update_influxdb.py` scripts were started correctly, you should be getting a response from the database!

Example:

```
from(bucket: "block_heights")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "block_height_request")
  |> filter(fn: (r) => r["url"] == "https://bsc-dataseed1.binance.org" or r["url"] == "https://bsc-dataseed1.defibit.io" or r["url"] == "https://bsc-dataseed1.ninicoin.io")
  |> filter(fn: (r) => r["_field"] == "block_height" or r["_field"] == "time_total")
```
