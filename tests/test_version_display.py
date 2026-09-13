# -*- coding: utf-8 -*-
import os
import sys
import unittest
from unittest.mock import patch


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import app as factory


class VersionDisplayTests(unittest.TestCase):
    def setUp(self):
        self.client = factory.app.test_client()

    def test_status_exposes_version_file_value(self):
        response_stub = type('Response', (), {'status_code': 503})()
        with patch.object(factory.requests, 'get', return_value=response_stub), \
                patch.object(factory, 'comfy_check', return_value=False), \
                patch.object(factory, 'find_ffmpeg', return_value=None), \
                patch.object(factory, 'acceleration_status', return_value={}):
            response = self.client.get('/api/status')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['version'], factory.app_version())

    def test_header_renders_status_version(self):
        with open(os.path.join(ROOT, 'index.html'), 'r', encoding='utf-8') as handle:
            page = handle.read()

        self.assertIn('id="app-version"', page)
        self.assertIn("currentVersion.startsWith('v')", page)


if __name__ == '__main__':
    unittest.main()
