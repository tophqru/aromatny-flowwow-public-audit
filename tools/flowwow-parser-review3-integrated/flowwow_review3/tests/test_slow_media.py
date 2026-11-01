import unittest
from unittest.mock import Mock, patch
import media_transport as media

class SlowMediaBudgets(unittest.TestCase):
    def response(self,status=200):
        response=Mock(status=status)
        response.getheader.side_effect=lambda k: '64' if k=='Content-Length' else None
        response.read1.side_effect=[b'x'*64,b'']
        return response

    def test_invalid_budgets_never_open_network(self):
        with patch.object(media,'open_response') as opening:
            for options in [dict(socket_timeout=0),dict(socket_timeout=61),dict(total_timeout=181),dict(socket_timeout=True),dict(socket_timeout=60,total_timeout=45)]:
                with self.assertRaises(ValueError):media.fetch_image('https://content.flowwow-images.com/a.jpg',1024,**options)
            opening.assert_not_called()

    def test_extended_budget_allows_slow_body_and_closes_resources(self):
        conn=Mock();response=self.response()
        with patch.object(media,'open_response',return_value=(conn,response)) as opening, patch.object(media.time,'monotonic',side_effect=[0,50,100]):
            self.assertEqual(media.fetch_image('https://content.flowwow-images.com/a.jpg',1024,socket_timeout=60,total_timeout=180),b'x'*64)
        opening.assert_called_once_with('https://content.flowwow-images.com/a.jpg',socket_timeout=60)
        response.close.assert_called_once();conn.close.assert_called_once()

    def test_default_total_budget_still_rejects_slow_body(self):
        conn=Mock();response=self.response()
        with patch.object(media,'open_response',return_value=(conn,response)),patch.object(media.time,'monotonic',side_effect=[0,46]):
            with self.assertRaisesRegex(RuntimeError,'TOTAL_TIME'):media.fetch_image('https://content.flowwow-images.com/a.jpg',1024)
        response.read1.assert_not_called();conn.close.assert_called_once()

    def test_extended_budget_does_not_retry_access_denials(self):
        for status in [401,403,429]:
            conn=Mock();response=self.response(status)
            with patch.object(media,'open_response',return_value=(conn,response)) as opening:
                with self.assertRaises(media.MediaAccessBlocked):media.fetch_image('https://content.flowwow-images.com/a.jpg',1024,socket_timeout=60,total_timeout=180)
                self.assertEqual(opening.call_count,1)
            response.read1.assert_not_called();conn.close.assert_called_once()
