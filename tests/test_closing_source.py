import base64
import io
import unittest
import zipfile
from unittest.mock import Mock, patch
from persistent_store import StorageError
from closing_source import fetch_closing_archive, COOLDOWN

class ClosingSourceTests(unittest.TestCase):
    def test_cached_bundle_never_downloads(self):
        store=Mock();store.get.return_value={'name':'saved.zip'}
        with patch('urllib.request.urlopen') as request:
            self.assertTrue(fetch_closing_archive(store)[1]);request.assert_not_called();store.reserve.assert_not_called()

    def test_missing_approval_prevents_reservation_and_download(self):
        store=Mock();store.get.return_value=None
        with patch('urllib.request.urlopen') as request:
            with self.assertRaises(ValueError):fetch_closing_archive(store)
        request.assert_not_called();store.reserve.assert_not_called()

    def test_quota_failure_prevents_network(self):
        store=Mock();store.get.return_value=None;store.reserve.side_effect=StorageError('blocked')
        with patch('urllib.request.urlopen') as request:
            with self.assertRaises(StorageError):fetch_closing_archive(store,approved=True)
            request.assert_not_called()

    def test_valid_zip_is_saved_with_shared_two_per_week_limit(self):
        raw=io.BytesIO()
        with zipfile.ZipFile(raw,'w') as z:z.writestr('E0.csv',b'Div,Date,HomeTeam,AwayTeam,FTHG,FTAG\n')
        store=Mock();store.get.return_value=None;store.reserve.return_value=9
        response=Mock();response.read.return_value=raw.getvalue()
        context=Mock();context.__enter__=Mock(return_value=response);context.__exit__=Mock(return_value=False)
        with patch('urllib.request.urlopen',return_value=context) as request:
            bundle,reused=fetch_closing_archive(store,approved=True)
        self.assertFalse(reused);self.assertEqual(base64.b64decode(bundle['content']),raw.getvalue());self.assertEqual(request.call_count,1)
        store.finish.assert_called_once_with(9,'success')
        self.assertEqual(store.reserve.call_args.kwargs,{'minimum_seconds':7,'weekly_limit':2})

    def test_failed_attempt_is_counted_and_not_retried(self):
        store=Mock();store.get.return_value=None;store.reserve.return_value=9
        with patch('urllib.request.urlopen',side_effect=OSError('offline')) as request:
            with self.assertRaises(OSError):fetch_closing_archive(store,approved=True)
        self.assertEqual(request.call_count,1);store.finish.assert_called_once_with(9,'failed',cooldown=COOLDOWN);store.put.assert_not_called()

if __name__=='__main__':unittest.main()
