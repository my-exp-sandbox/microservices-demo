import unittest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(__file__), '../recommendationservice'))
from customerserviceagent import create_app

class CustomerServiceAgentTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app().test_client()

    def test_order_status(self):
        response = self.app.get('/order-status?user_id=test')
        self.assertEqual(response.status_code, 200)
        self.assertIn('order_status', response.get_json())

    def test_track_order(self):
        response = self.app.get('/track-order?tracking_id=test')
        self.assertEqual(response.status_code, 200)
        self.assertIn('tracking_info', response.get_json())

    def test_faq(self):
        response = self.app.get('/faq?question=shipping')
        self.assertEqual(response.status_code, 200)
        self.assertIn('answer', response.get_json())

if __name__ == '__main__':
    unittest.main()
