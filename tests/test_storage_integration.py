import ast
import datetime as dt
import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import urllib
import urllib.error
import urllib.request
from persistent_store import content_key, StorageError
from archive_audit import valid_score
from regular_time_correction import provider_final_fields


def functions():
    tree=ast.parse(Path('app.py').read_text())
    wanted={'api_matches','convert','restore_types','ApiError'}
    module=ast.Module(body=[x for x in tree.body if isinstance(x,(ast.FunctionDef,ast.ClassDef)) and x.name in wanted],type_ignores=[])
    ns=dict(hashlib=hashlib,json=json,urllib=urllib,STORE=None,valid_score=valid_score,provider_final_fields=provider_final_fields)
    exec(compile(module,'app.py','exec'),ns)
    return ns


class ArchiveTests(unittest.TestCase):
    def test_signatures_round_trip(self):
        signature=(12,'2026-10-24','CSV',.16,(('PL','Example','2026-01-01'),))
        self.assertEqual(functions()['restore_types'](json.loads(json.dumps(signature))),signature)
        self.assertEqual(content_key({'signature':signature}), content_key(json.loads(json.dumps({'signature':signature}))))

    def test_cache_hit_never_calls_provider(self):
        ns=functions(); store=Mock(); store.get.return_value=[{'id':42}]; ns['STORE']=store
        with patch('urllib.request.urlopen') as request:
            self.assertEqual(ns['api_matches']('test-key','PL',2026),[{'id':42}])
            request.assert_not_called(); store.reserve.assert_not_called()

    def test_reservation_failure_prevents_download(self):
        ns=functions();store=Mock();store.get.return_value=None;store.reserve.side_effect=StorageError('blocked');ns['STORE']=store
        with patch('urllib.request.urlopen') as request:
            with self.assertRaises(StorageError): ns['api_matches']('test-key','PL',2026)
            request.assert_not_called()

    def test_success_archives_response_after_reservation(self):
        ns=functions();store=Mock();store.get.return_value=None;store.reserve.return_value=7;ns['STORE']=store
        response=Mock();response.read.return_value=b'{"matches":[{"id":42}]}'
        context=Mock();context.__enter__=Mock(return_value=response);context.__exit__=Mock(return_value=False)
        with patch('urllib.request.urlopen',return_value=context) as request:
            ns['api_matches']('test-key','PL',2026)
        store.reserve.assert_called_once_with('football-data.org','PL:2026')
        store.put_api_matches.assert_called_once();store.finish.assert_called_once_with(7,'success')
        self.assertNotIn('test-key',str(store.mock_calls))

    def test_rate_limit_records_cooldown_and_does_not_cache(self):
        ns=functions();store=Mock();store.get.return_value=None;store.reserve.return_value=7;ns['STORE']=store
        import io
        error=urllib.error.HTTPError('https://example.invalid',429,'rate limit',{'Retry-After':'120'},io.BytesIO(b'wait'))
        with patch('urllib.request.urlopen',side_effect=error):
            with self.assertRaises(ns['ApiError']): ns['api_matches']('test-key','PL',2026)
        store.finish.assert_called_once_with(7,'HTTP 429',120);store.put_api_matches.assert_not_called()

    def test_invalid_token_is_authentication_failure_even_with_http_400(self):
        ns=functions()
        self.assertTrue(ns['ApiError'](400,'{"message":"Your API token is invalid.","errorCode":400}').authentication_failed)
        self.assertFalse(ns['ApiError'](400,'Unknown season').authentication_failed)

    def test_empty_token_stops_before_network_or_reservation(self):
        ns=functions(); ns['STORE']=Mock()
        with patch('urllib.request.urlopen') as request:
            with self.assertRaises(ns['ApiError']): ns['api_matches']('   ','PL',2026)
            request.assert_not_called(); ns['STORE'].reserve.assert_not_called()

    def test_convert_rejects_invalid_final_scores(self):
        for bad in (True,-1,1.5,'NaN',None):
            history,fixtures=functions()['convert']([dict(utcDate='2026-10-20T12:00:00Z',homeTeam=dict(name='H'),awayTeam=dict(name='A'),status='FINISHED',score=dict(fullTime=dict(home=bad,away=0)))],'PL',2026)
            self.assertEqual(history,[]);self.assertEqual(fixtures,[])

    def test_convert_preserves_model_input(self):
        ns=functions()
        history,fixtures=ns['convert']([{'utcDate':'2026-10-20T12:00:00Z','homeTeam':{'name':'H'},'awayTeam':{'name':'A'},'status':'FINISHED','score':{'fullTime':{'home':2,'away':1}}}],'PL')
        self.assertEqual(len(history),1)
        expected={'date':'2026-10-20','league':'PL','home':'H','away':'A','home_goals':2,'away_goals':1}
        for key,value in expected.items():
            self.assertEqual(history[0][key],value)
        self.assertEqual(history[0]['kickoff_utc'],'2026-10-20T12:00:00Z')
        self.assertEqual(history[0]['source'],'football-data.org')
        self.assertEqual(history[0]['match_id'],'')
        self.assertEqual(fixtures,[])

if __name__=='__main__': unittest.main()
