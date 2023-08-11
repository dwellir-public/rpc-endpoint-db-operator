<!--
Avoid using this README file for information that is maintained or published elsewhere, e.g.:

* metadata.yaml > published on Charmhub
* documentation > published on (or linked to from) Charmhub
* detailed contribution guide > documentation or CONTRIBUTING.md

Use links instead.
-->

# rpc-endpoint-db-operator

Charmhub package name: rpc-endpoint-db
More information: https://charmhub.io/rpc-endpoint-db

This charm runs an application that maintains and serves a database of RPC endpoints for blockchain nodes. The database and its API is built with SQLite and [Flask](https://flask.palletsprojects.com/en/2.3.x/), and it is served by the WSGI server [Gunicorn](https://flask.palletsprojects.com/en/2.3.x/deploying/gunicorn/).

## Setup

The charm installs all required software in its container, including the Python libraries used by the Flask app. If you would like to do a manual deployment of the app, for development purposes or similar, just follow the steps taken by [the charm](src/charm.py). Note: for a local deployment it is advised that you make use of a Python virtual environment.

### API authentication

The charm automatically generates the authentication files that are needed to run the application; `auth_jwt_secret_key` and `auth_password`. They need to be in the container's root folder, together with the `app.py` script, in order for the app to run. If you're doing a re-deploy, or for some other reason want to re-use an earlier secret key or auth password you can simply overwrite the files that were generated at charm install. If a need for new keys arise, they can be generated like thus:

    openssl rand -hex 32 > key_filename

In order to make database changes over the application's API, e.g. posting a `/create_chain` request, you'll first need to generate an access token using the `/token` endpoint. To do this over the API, you'll need the auth password. The auth password, as mentioned, is found in the root folder of the charm's container. It can also be accessed through an action, which also happens to be a way to get the access token directly.

    juju run-action rpc-endpoint-db/0 get-auth-pw --wait
    juju run-action rpc-endpoint-db/0 get-access-token --wait

## Usage

When the charm has started the [systemd](https://wiki.archlinux.org/title/systemd) service serving the application it will be accessible on the port designated by the configuration (default is port 8000). This is the access point that should be set to the [blockchain-monitor's](https://github.com/dwellir-public/blockchain-monitor-operator) configuration, the application this endpoint database was made to serve.

There are two main reasons to interact with the app and its database after a deployment. The first is to populate a newly deployed app with the current list of chains and endpoints that should be tracked. The second reason is to update that list when the situation changes. To ease interaction with the application there is a utility script, [db_util.py](templates/db_util.py). It can be run either from your local clone of this repo or from the charm's container, where it is copied during the install and subsequent charm upgrades.

### Query via db_util.py

The [db_util.py](templates/db_util.py) script holds a number of utility functions to interact directly with the database, should it be run from the app's container, or to make requests to the Flask API more easily than it would be through manual `curl`-ing. Some examples below.

#### Uses API

    # Export data via API URL to default out location
    python3 db_util.py export --source_url http://<IP of app's container>:8000

    # Delete an RPC URL
    python3 db_util.py request --url <URL> --auth-pw <PW> delete_rpc https://rpc.pulsechain.com

    # List chains in DB
    python3 db_util.py request --url <URL> chains

#### Requires local access to DB file

    # Import data from default db_json location to local database
    python3 db_util.py import --target_db <DB file>

    # Check connectivity to RPC endpoints with "polkadot" in their URL
    python3 db_util.py json <folder with chains, RPC:s in JSON> -f polkadot

### Directly query the Flask API

Sometimes one needs to make manual queries to the API, and here follows some examples for that:

Create a chain record

    curl -X POST -H "Content-Type: application/json" -d \
    '{
        "name": "TESTCHAIN",
        "api_class": "substrate"
    }' \
    http://localhost:8000/create_chain

Create a URL record

    curl -X POST -H 'Content-Type: application/json' -d \
    '{
        "url": "https://foo.bar",
        "chain_name": "TESTCHAIN"
    }' \
    http://localhost:8000/create_rpc_url

Get the URL record

    curl -X GET -H 'http://localhost:8000/get_url?protocol=https&address=foo.bar'

Update the URL record

    curl -X PUT -H 'Content-Type: application/json' -d \
    '{
        "url": "https://foofoo.bar",
        "chain_name": "chain6"
    }' \
    http://localhost:8000/update_url?protocol=https&address=foo.bar

Delete a URL record

    curl -X DELETE http://localhost:8000/delete_url/?protocol=https&address=foofoo.bar

Get all records

    curl http://localhost:8000/all/chains
    curl http://localhost:8000/all/rpc_urls

Get an access token (`username` is hardcoded and `password` is retrieved from where the app is hosted, see [API authentication](#api-authentication))

    curl -X POST -d '{"username": "dwellir_endpointdb", "password": <password>}' -H 'Content-Type: application/json' http://localhost:8000/token

Use access token in a query

    curl -H 'Authorization: Bearer <token>' http://localhost:8000/protected-endpoint

## Other resources

- Endpoint resources:
  - [EVM chains on chainlist.org](https://chainlist.org/)
  - [Polkadot chains on polkadot.js](https://polkadot.js.org/apps/#/explorer)
- [Contributing](CONTRIBUTING.md)
- See the [Juju SDK documentation](https://juju.is/docs/sdk) for more information about developing and improving charms.
