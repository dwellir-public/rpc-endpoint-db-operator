#!/bin/env python3

import os
import sqlite3
import tempfile
import unittest
import json
from app import app, create_table_if_not_exist


class CRUDTestCase(unittest.TestCase):

    access_token = ""

    def setUp(self):
        app.config['TESTING'] = True

        self.db_fd, app.config['DATABASE'] = tempfile.mkstemp(prefix='unittest_database_', suffix='.db')

        # Initialize the test database with schema and test data
        with app.app_context():
            self.init_db()
            self.populate_db()

        self.app = app.test_client()

        # Reference data.
        self.data_1 = {
            'native_id': 1,
            'chain_name': 'Ethereum',
            'urls': [
                'https://foo/bar',
                'wss://fish/dog:9000'
            ]
        }
        self.data_2 = {
            'native_id': 2,
            'chain_name': 'Bitcoin',
            'urls': [
                'https://bit/bar',
                'wss://smoke/hammer:1234'
            ]
        }

        self.access_token = self.app.post('/token', json={'username': 'tmp', 'password': 'tmp'}).json['access_token']

    def tearDown(self):
        # Close the database connection and remove the temporary test database
        os.close(self.db_fd)
        os.unlink(app.config['DATABASE'])
        print(app.config['DATABASE'])

    def init_db(self):
        # Use the same create_table as for the live database.
        create_table_if_not_exist()

    def populate_db(self):
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        c.execute("INSERT INTO chains_public_rpcs (native_id, chain_name, urls, api_class) VALUES (?, ?, ?, ?)",
                  (1, "Ethereum", '["https://eth1-archive-1.dwellir.com", "wss://eth1-archive-2.dwellir.com"]', 'ethereum'))
        c.execute("INSERT INTO chains_public_rpcs (native_id, chain_name, urls, api_class) VALUES (?, ?, ?, ?)",
                  (2, "Binance Smart Chain", '["https://bsc-dataseed1.binance.org","https://bsc.publicnode.com","wss://bsc-ws-node.nariox.org"]', 'ethereum'))
        conn.commit()
        conn.close()

    def test_create_record_missing_entry(self):
        # Send a request without the urls entry
        data = {'native_id': 1, 'chain_name': 'Ethereum'}
        response = self.app.post('/create', json=data)
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json)

        # Send a request without the chain_name entry
        data = {'native_id': 1, 'urls': ['https://mainnet.infura.io/v3/...', 'https://ropsten.infura.io/v3/...']}
        response = self.app.post('/create', json=data)
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json)

        # Send a request without the native_id entry
        data = {'chain_name': 'Ethereum', 'urls': ['https://mainnet.infura.io/v3/...', 'https://ropsten.infura.io/v3/...']}
        response = self.app.post('/create', json=data)
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json)

    def test_create_record_no_duplicate_names(self):
        # Send a request with all three entries
        data = {'native_id': 1, 'chain_name': 'Ethereum', 'urls': ['https://mainnet.infura.io/v3/...', 'https://ropsten.infura.io/v3/...']}
        response = self.app.post('/create', json=data)
        self.assertEqual(response.status_code, 400)

    def test_create_record_success(self):
        # Send a request with all three entries
        data = {'native_id': 999,
                'chain_name': 'TESTNAME',
                'urls': ['https://foo.bar', 'https://foo.bar'],
                'api_class': 'substrate'}
        response = self.app.post('/create', json=data)
        print("===============", response)
        self.assertEqual(response.status_code, 201)
        self.assertIn('message', response.json)

        # Check that the record was inserted into the database
        conn = sqlite3.connect(app.config['DATABASE'])
        c = conn.cursor()
        c.execute('SELECT * FROM chains_public_rpcs WHERE id = ?', (response.json['id'],))
        record = c.fetchone()
        conn.close()
        self.assertIsNotNone(record)
        self.assertEqual(record[1], data['native_id'])
        self.assertEqual(record[2], data['chain_name'])
        self.assertEqual(json.loads(record[3]), data['urls'])

    def test_get_all_records(self):
        response = self.app.get('/all')
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json, list)

    def test_get_record_by_id(self):
        chaindata = {
            'native_id': 2,
            'chain_name': 'Bitcoin',
            'urls': [
                'https://bit/bar',
                'wss://smoke/hammer:1234'
            ],
            'api_class': 'aptos'
        }
        response = self.app.post('/create', json=chaindata)
        record_id = response.json['id']
        response = self.app.get(f'/get/{record_id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['chain_name'], chaindata['chain_name'])

    def test_update_record(self):
        # Create a new record
        chaindata = {
            'native_id': 2,
            'chain_name': 'Bitcoin 2',
            'urls': [
                'https://bit/bar',
                'wss://smoke/hammer:1234'
            ],
            'api_class': 'substrate'
        }
        create_response = self.app.post('/create', json=chaindata)
        record_id = create_response.json['id']

        # Update the record
        new_data = {'native_id': 2,
                    'chain_name': 'test-update-chainName',
                    'urls': ['https://dwellir.com:455'],
                    'api_class': 'ethereum'}
        update_response = self.app.put('/update/{}'.format(record_id), json=new_data)
        assert update_response.status_code == 200

        # Get the updated record and check its values
        get_response = self.app.get('/get/{}'.format(record_id))
        updated_record = get_response.json
        assert updated_record['native_id'] == new_data['native_id']
        assert updated_record['chain_name'] == new_data['chain_name']
        print("##############", new_data['api_class'], updated_record['api_class'])
        assert updated_record['api_class'] == new_data['api_class']
        actual_urls = updated_record['urls']
        self.assertListEqual(new_data['urls'], actual_urls)

    def test_delete_record(self):
        chaindata = {
            'native_id': 2,
            'chain_name': 'Bitcoin 2',
            'urls': [
                'https://bit/bar',
                'wss://smoke/hammer:1234'
            ],
            'api_class': 'substrate'
        }
        response = self.app.post('/create', json=chaindata)
        record_id = response.json['id']
        response = self.app.delete(f'/delete/{record_id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['message'], 'Record deleted successfully')

    def test_get_chain_info_by_chain_name(self):
        response = self.app.get('/chain_info?chain_name=Ethereum')
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json, msg='Response is not valid JSON')
        self.assertGreaterEqual(len(response.json), 1)
        self.assertEqual(response.json[0]['id'], 1)
        self.assertEqual(response.json[0]['native_id'], 1)
        self.assertEqual(response.json[0]['chain_name'], 'Ethereum')
        self.assertIsInstance(response.json[0]['urls'], list)

    def test_get_chain_info_by_native_id(self):
        response = self.app.get('/chain_info?native_id=1')
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.json), 1)
        self.assertIsNotNone(response.json, msg='Response is not valid JSON')
        self.assertEqual(response.json[0]['id'], 1)
        self.assertEqual(response.json[0]['native_id'], 1)
        self.assertEqual(response.json[0]['chain_name'], 'Ethereum')
        self.assertIsInstance(response.json[0]['urls'], list)

    def test_get_chain_info_missing_params(self):
        response = self.app.get('/chain_info')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['error'], 'Missing required parameters')

    def test_get_chain_info_not_found(self):
        response = self.app.get('/chain_info?chain_name=Foo')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json['error'], 'Chain not found')

    def test_jwt_protection(self):
        response = self.app.get('/protected', headers={'Authorization': f'Bearer {self.access_token}'})
        self.assertEqual(response.json['logged_in_as'], 'tmp')


if __name__ == '__main__':
    unittest.main()
