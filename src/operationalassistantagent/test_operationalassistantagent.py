import unittest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from operationalassistantagent import create_app

class OperationalAssistantAgentTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app().test_client()

    def test_system_status(self):
        response = self.app.get('/system-status')
        self.assertEqual(response.status_code, 200)
        self.assertIn('status', response.get_json())

    def test_troubleshoot(self):
        response = self.app.get('/troubleshoot?service=adservice')
        self.assertEqual(response.status_code, 200)
        self.assertIn('logs', response.get_json())

if __name__ == '__main__':
    unittest.main()
