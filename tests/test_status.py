from __future__ import annotations

import unittest

from server.app import app

class TestStatusApi(unittest.TestCase):
    def test_modes_status_api(self):
        client = app.test_client()
        result = client.get("/api/modes/status").get_json()

        self.assertTrue(result["ok"])
        self.assertEqual(result["modes"]["rooms"]["status"], "available")
        self.assertEqual(result["modes"]["match"]["status"], "available")
        self.assertEqual(result["modes"]["ai"]["status"], "available")

if __name__ == "__main__":
    unittest.main()
