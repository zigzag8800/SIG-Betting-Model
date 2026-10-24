"""One small season archive, cached permanently, no automatic retries.

The source permits light automated personal-use downloads. Old downloads outside
this register cannot be reconstructed. New requests are limited to two per seven
days across all app sessions, and failed attempts consume the same allowance.
"""
import base64
import io
import urllib.request
import zipfile
from bookmaker_lab import expand_historical_files
from types import SimpleNamespace

PROVIDER='football-data.co.uk'
RESOURCE='2526/data.zip'
URL='https://football-data.co.uk/mmz4281/2526/data.zip'
COOLDOWN=60
MAX_BYTES=20*1024*1024


def fetch_closing_archive(store, approved=False):
    """Reserve in DB BEFORE IO; every later use reads the saved original ZIP."""
    cached=store.get('provider_bundle',PROVIDER+':'+RESOURCE)
    if cached is not None:
        return cached,True
    if not approved:
        raise ValueError('Nyt download kræver din udtrykkelige godkendelse.')
    reservation=store.reserve(PROVIDER,RESOURCE,minimum_seconds=7,weekly_limit=2)
    try:
        req=urllib.request.Request(URL,headers={'User-Agent':'SIG-Betting-Model/3.8 personal research','Accept':'application/zip'})
        with urllib.request.urlopen(req,timeout=45) as response:
            raw=response.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES or not zipfile.is_zipfile(io.BytesIO(raw)):
            raise ValueError('Kilden returnerede ikke en gyldig ZIP under 20 MB.')
        # Validate contents before putting the original archive into durable storage.
        source=SimpleNamespace(name='football_data_2025_26.zip',getvalue=lambda:raw)
        files=expand_historical_files([source])
        bundle={'name':source.name,'content':base64.b64encode(raw).decode('ascii'),
                'url':URL,'provider':PROVIDER,'resource':RESOURCE,
                'divisions':[f.name.rsplit('/',1)[-1].removesuffix('.csv') for f in files]}
        store.put('provider_bundle',PROVIDER+':'+RESOURCE,bundle)
        store.finish(reservation,'success')
        return bundle,False
    except Exception:
        store.finish(reservation,'failed',cooldown=COOLDOWN)
        raise
