import unittest
from flask import Flask, session, jsonify
from flask.testing import FlaskClient
from main import app, default_videos, search_videos, next_page, prev_page, summarize


class TestFlaskApp(unittest.TestCase):
    @classmethod
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        with self.app.session_transaction() as sess:
            sess['next_page_token'] = 'NEXT_PAGE_TOKEN'
            sess['prev_page_token'] = 'PREV_PAGE_TOKEN'

    def test_home(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'tubenotes', response.data)

    def test_videos(self):
        response = self.app.get('/videos')
        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.json)

    def test_search(self):
        response = self.app.get('/search', query_string={'query': 'test'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.json)

    def load_videos(self):
        self.app.get('/videos')

    def next_page(self):
        self.app.get('/next')

    def test_next(self):
        # Test default videos next page
        self.load_videos()
        response = self.app.get('/next')
        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.json)

        # Test video search next page
        self.app.get('/search', query_string={'query': 'test'})
        response = self.app.get('/next', query_string={'query': 'test'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.json)

    def test_prev(self):
        # Test default videos previous page
        self.load_videos()
        self.next_page()
        response = self.app.get('/prev')
        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.json)

        # Test video search previous page
        self.app.get('/search', query_string={'query': 'test'})
        self.app.get('/next', query_string={'query': 'test'})
        response = self.app.get('/prev', query_string={'query': 'test'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.json)

    def test_summarize_medium(self):
        # Medium-length video
        response = self.app.get('/summarize', query_string={'videoId': 'GisSNuVpbkM'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('summary', response.json)
    
    def test_summarize_long(self):
        # Long video
        response = self.app.get('/summarize', query_string={'videoId': 'B6kg2zeJ9do'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('summary', response.json)

if __name__ == '__main__':
    unittest.main()
