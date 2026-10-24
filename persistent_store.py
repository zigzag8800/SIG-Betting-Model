"""Private PostgreSQL archive. No credentials or provider data belong in Git."""
import hashlib
import json
import datetime as dt


class StorageError(RuntimeError):
    pass


class Store:
    def __init__(self, dsn):
        import psycopg
        self.psycopg = psycopg
        self.dsn = dsn

    def connect(self):
        # Require encrypted transport even if a copied URL requests otherwise.
        return self.psycopg.connect(self.dsn, sslmode='require', connect_timeout=10)

    def initialize(self):
        with self.connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS sig_archive (
                kind text NOT NULL, key text NOT NULL, payload jsonb NOT NULL,
                saved_at timestamptz NOT NULL DEFAULT now(),
                PRIMARY KEY(kind,key))''')
            conn.execute('''CREATE TABLE IF NOT EXISTS sig_downloads (
                id bigserial PRIMARY KEY, provider text NOT NULL, resource text NOT NULL,
                attempted_at timestamptz NOT NULL DEFAULT now(), status text NOT NULL,
                blocked_until timestamptz)''')
            conn.execute('CREATE INDEX IF NOT EXISTS sig_download_provider_time ON sig_downloads(provider, attempted_at)')

    def put(self, kind, key, payload):
        if kind in ('api_matches','api_matches_version','api_matches_observation','api_matches_head'):
            raise StorageError('API cache must use the versioned response writer.')
        from psycopg.types.json import Jsonb
        with self.connect() as conn:
            conn.execute('''INSERT INTO sig_archive(kind,key,payload) VALUES(%s,%s,%s)
                ON CONFLICT(kind,key) DO UPDATE SET payload=excluded.payload,saved_at=now()''',
                (kind,key,Jsonb(payload)))

    def get(self, kind, key, max_age=None):
        with self.connect() as conn:
            row=conn.execute('SELECT payload, saved_at FROM sig_archive WHERE kind=%s AND key=%s', (kind,key)).fetchone()
        if not row:
            return None
        if max_age is not None and (dt.datetime.now(dt.timezone.utc)-row[1]).total_seconds()>max_age:
            return None
        return row[0]

    @staticmethod
    def _api_version(conn,cache_key,matches,saved_at,origin,raw_response=None):
        from psycopg.types.json import Jsonb
        digest=content_key(raw_response if raw_response is not None else matches);version_key=cache_key+':'+digest
        payload=dict(cache_key=cache_key,payload_hash=digest,matches=matches,origin=origin,raw_scope='full_json' if raw_response is not None else 'matches_only')
        if raw_response is not None:payload['response']=raw_response
        inserted=conn.execute("""INSERT INTO sig_archive(kind,key,payload,saved_at)
            VALUES('api_matches_version',%s,%s,%s) ON CONFLICT(kind,key) DO NOTHING""",
            (version_key,Jsonb(payload),saved_at)).rowcount
        if not inserted:
            stored=conn.execute("SELECT payload FROM sig_archive WHERE kind='api_matches_version' AND key=%s",(version_key,)).fetchone()
            if not stored or not api_version_valid(version_key,stored[0]):
                raise StorageError('Existing raw API version failed checksum validation.')
        return version_key,inserted

    @classmethod
    def _retain_cached_api_version(cls,conn,cache_key,matches,saved_at):
        from psycopg.types.json import Jsonb
        existing=conn.execute("SELECT key,payload FROM sig_archive WHERE kind='api_matches_version' AND payload->>'cache_key'=%s AND payload->'matches'=%s LIMIT 1",(cache_key,Jsonb(matches))).fetchone()
        if existing:
            payload=existing[1];digest=content_key(payload.get('response',payload.get('matches')))
            if not api_version_valid(existing[0],payload):
                raise StorageError('Existing raw API version failed checksum validation.')
            return existing[0],0
        return cls._api_version(conn,cache_key,matches,saved_at,'legacy_cache_saved_at')

    def save_api_response(self,cache_key,matches,reservation,raw_response=None):
        """Commit raw versions, observation, cache pointer and success together.

        Latest reservation selects the cache, not whichever HTTP response arrived
        last. Neither ordering nor ingestion time establishes historical known_at.
        """
        from psycopg.types.json import Jsonb
        if not isinstance(matches,list):raise ValueError('API matches must be a list')
        if raw_response is not None and (not isinstance(raw_response,dict) or raw_response.get('matches')!=matches):
            raise ValueError('Full API response must contain the same matches')
        parts=cache_key.rsplit(':',2)
        if len(parts)!=3:raise ValueError('Invalid API cache key')
        resource=':'.join(parts[1:]);digest=content_key(raw_response if raw_response is not None else matches)
        with self.connect() as conn:
            conn.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',('sig:api:'+cache_key,))
            current=conn.execute("SELECT payload,saved_at FROM sig_archive WHERE kind='api_matches' AND key=%s FOR UPDATE",(cache_key,)).fetchone()
            prior=conn.execute("SELECT payload FROM sig_archive WHERE kind='api_matches_observation' AND key=%s",(str(reservation),)).fetchone()
            if prior:
                if prior[0]['cache_key']!=cache_key or prior[0]['payload_hash']!=digest:
                    raise StorageError('Download reservation already has different archived content.')
                if current is None:raise StorageError('Archived observation has no cache pointer.')
                return current[0]
            reserved=conn.execute("SELECT provider,resource,status FROM sig_downloads WHERE id=%s FOR UPDATE",(reservation,)).fetchone()
            if reserved!=('football-data.org',resource,'reserved'):
                raise StorageError('No matching active download reservation.')
            now=conn.execute('SELECT clock_timestamp()').fetchone()[0]
            if current:self._retain_cached_api_version(conn,cache_key,current[0],current[1])
            version_key,_=self._api_version(conn,cache_key,matches,now,'response_archived_at',raw_response)
            head=conn.execute("SELECT payload FROM sig_archive WHERE kind='api_matches_head' AND key=%s",(cache_key,)).fetchone()
            selected=head is None or reservation>int(head[0]['download_id'])
            observation=dict(cache_key=cache_key,payload_hash=digest,version_key=version_key,
                download_id=reservation,recorded_at=now.isoformat(),selected_as_cache=selected)
            conn.execute("INSERT INTO sig_archive(kind,key,payload) VALUES('api_matches_observation',%s,%s)",
                         (str(reservation),Jsonb(observation)))
            if selected:
                for kind,payload in (('api_matches',matches),('api_matches_head',observation)):
                    conn.execute("""INSERT INTO sig_archive(kind,key,payload,saved_at) VALUES(%s,%s,%s,%s)
                        ON CONFLICT(kind,key) DO UPDATE SET payload=excluded.payload,saved_at=excluded.saved_at""",
                        (kind,cache_key,Jsonb(payload),now))
            conn.execute("UPDATE sig_downloads SET status='success',blocked_until=NULL WHERE id=%s",(reservation,))
            return matches if selected else current[0]

    def backfill_api_versions(self):
        """Preserve existing cache without refreshing TTL or contacting providers."""
        added=checked=0
        with self.connect() as conn:
            keys=conn.execute("SELECT key FROM sig_archive WHERE kind='api_matches' ORDER BY key").fetchall()
            for (cache_key,) in keys:
                conn.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',('sig:api:'+cache_key,))
                row=conn.execute("SELECT payload,saved_at FROM sig_archive WHERE kind='api_matches' AND key=%s FOR UPDATE",(cache_key,)).fetchone()
                if row:
                    _,inserted=self._retain_cached_api_version(conn,cache_key,row[0],row[1])
                    added+=inserted;checked+=1
        return dict(cache_items_checked=checked,versions_added=added,provider_downloads=0,cache_ttl_changed=False)

    def audit_snapshot(self):
        """Inspect all record kinds without modifying data or provider ledgers."""
        with self.connect() as conn:
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            inventory=[dict(zip(('kind','records','bytes'),r)) for r in conn.execute(
                'SELECT kind,count(*),sum(pg_column_size(payload)) FROM sig_archive GROUP BY kind ORDER BY kind').fetchall()]
            current=conn.execute("SELECT payload FROM sig_archive WHERE kind='workspace' AND key='current'").fetchone()
            api=conn.execute("SELECT key,payload FROM sig_archive WHERE kind='api_matches' ORDER BY key").fetchall()
            api_versions=conn.execute("SELECT key,payload,saved_at FROM sig_archive WHERE kind='api_matches_version' ORDER BY key").fetchall()
            api_observations=conn.execute("SELECT payload FROM sig_archive WHERE kind='api_matches_observation' ORDER BY key").fetchall()
            versions=[dict(zip(('saved_at','history','fixtures','research'),r)) for r in conn.execute(
                "SELECT saved_at,jsonb_array_length(COALESCE(payload->'history','[]'::jsonb)),jsonb_array_length(COALESCE(payload->'fixtures','[]'::jsonb)),jsonb_array_length(COALESCE(payload->'research_competitions_40','[]'::jsonb)) FROM sig_archive WHERE kind='workspace_version' ORDER BY saved_at").fetchall()]
            files=conn.execute("SELECT key,payload FROM sig_archive WHERE kind='source_csv' ORDER BY key").fetchall()
            bundles=conn.execute("SELECT key,payload FROM sig_archive WHERE kind='provider_bundle' ORDER BY key").fetchall()
            old_workspaces=conn.execute("SELECT key,jsonb_build_object('history',COALESCE(payload->'history','[]'::jsonb),'fixtures',COALESCE(payload->'fixtures','[]'::jsonb),'research_competitions_40',COALESCE(payload->'research_competitions_40','[]'::jsonb)) FROM sig_archive WHERE kind='workspace_version' ORDER BY key").fetchall()
        return dict(inventory=inventory,current=current[0] if current else None,api=api,versions=versions,files=files,old_workspaces=old_workspaces,bundles=bundles,api_versions=api_versions,api_observations=[r[0] for r in api_observations])

    def reserve(self, provider, resource, minimum_seconds=7, weekly_limit=None):
        """Commit reservation BEFORE network IO. Crashes still consume quota.

        Advisory lock serializes all sessions and workers for a provider.
        A failed database connection must prevent the request, never bypass it.
        """
        with self.connect() as conn:
            conn.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', ('sig:'+provider,))
            blocked=conn.execute('SELECT max(blocked_until) FROM sig_downloads WHERE provider=%s', (provider,)).fetchone()[0]
            now=conn.execute('SELECT now()').fetchone()[0]
            if blocked and blocked>now:
                raise StorageError('Leverandørens ventetid er ikke udløbet.')
            recent=conn.execute("SELECT count(*) FROM sig_downloads WHERE provider=%s AND attempted_at>now()-(%s * interval '1 second')", (provider, minimum_seconds)).fetchone()[0]
            if recent:
                raise StorageError('Vent lidt før næste download; et andet kald er netop registreret.')
            if weekly_limit is not None:
                count=conn.execute("SELECT count(*) FROM sig_downloads WHERE provider=%s AND attempted_at>now()-interval '7 days'", (provider,)).fetchone()[0]
                if count>=weekly_limit:
                    raise StorageError('Downloadgrænsen for de seneste syv døgn er nået.')
            return conn.execute("INSERT INTO sig_downloads(provider,resource,status) VALUES(%s,%s,'reserved') RETURNING id", (provider,resource)).fetchone()[0]

    def finish(self, reservation, status, cooldown=0):
        with self.connect() as conn:
            conn.execute("UPDATE sig_downloads SET status=%s, blocked_until=CASE WHEN %s>0 THEN now()+(%s * interval '1 second') ELSE NULL END WHERE id=%s", (status,cooldown,cooldown,reservation))

    def log(self):
        with self.connect() as conn:
            rows=conn.execute('SELECT provider,resource,attempted_at,status FROM sig_downloads ORDER BY id DESC LIMIT 100').fetchall()
        return [dict(zip(('Leverandør','Ressource','Tidspunkt','Status'),row)) for row in rows]


    def save_workspace(self, snapshot, expected):
        """Do not silently overwrite work saved by another browser session."""
        from psycopg.types.json import Jsonb
        fingerprint=content_key(snapshot)
        with self.connect() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtext('sig:workspace'))")
            row=conn.execute("SELECT payload FROM sig_archive WHERE kind='workspace' AND key='current'").fetchone()
            if (content_key(row[0]) if row else None)!=expected:
                raise StorageError('En anden session har ændret arkivet. Genindlæs før du fortsætter.')
            for kind,key in (('workspace_version',fingerprint),('workspace','current')):
                conn.execute('''INSERT INTO sig_archive(kind,key,payload) VALUES(%s,%s,%s)
                    ON CONFLICT(kind,key) DO UPDATE SET payload=excluded.payload,saved_at=now()''', (kind,key,Jsonb(snapshot)))
        return fingerprint

def content_key(payload):
    return hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()


def api_version_valid(key,payload):
    if not isinstance(payload,dict) or not isinstance(payload.get('matches'),list):return False
    response=payload.get('response',payload['matches'])
    if 'response' in payload and (not isinstance(response,dict) or response.get('matches')!=payload['matches']):return False
    expected_scope='full_json' if 'response' in payload else 'matches_only'
    digest=content_key(response)
    return payload.get('raw_scope')==expected_scope and payload.get('payload_hash')==digest and key==str(payload.get('cache_key',''))+':'+digest


def verify_store(store):
    """Exercise real SQL through fresh connections, without provider HTTP calls.

    Uses separate, uniquely named diagnostic records; existing user data and
    provider download budgets are never modified.
    """
    import uuid
    from concurrent.futures import ThreadPoolExecutor
    marker=uuid.uuid4().hex
    other=Store(store.dsn)
    payload={'marker':marker,'purpose':'storage verification'}
    store.put('diagnostic',marker,payload)
    if other.get('diagnostic',marker)!=payload:
        raise StorageError('Læsning fra en ny databaseforbindelse fejlede.')
    provider='diagnostic:'+marker
    first=store.reserve(provider,'quota-test',minimum_seconds=0,weekly_limit=1)
    try:
        other.reserve(provider,'quota-test',minimum_seconds=0,weekly_limit=1)
    except StorageError:
        pass
    else:
        raise StorageError('Den fælles downloadkvote blev ikke håndhævet.')
    store.finish(first,'diagnostic',cooldown=60)
    try:
        other.reserve(provider,'cooldown-test',minimum_seconds=0)
    except StorageError:
        pass
    else:
        raise StorageError('Ventetiden blev ikke bevaret på tværs af forbindelser.')
    def competing_request(_):
        try:
            other.reserve(provider+':concurrent','lock-test',minimum_seconds=0,weekly_limit=1)
            return True
        except StorageError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        if sum(pool.map(competing_request,range(2)))!=1:
            raise StorageError('Samtidige kald kunne omgå downloadgrænsen.')
    report={'checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),
            'read_write':True,'new_connection':True,'weekly_quota':True,
            'cooldown':True,'concurrent_lock':True,'provider_downloads':0}
    store.put('diagnostic','latest',report)
    return report
