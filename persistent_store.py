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

    def audit_snapshot(self):
        """Inspect all record kinds without modifying data or provider ledgers."""
        with self.connect() as conn:
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            inventory=[dict(zip(('kind','records','bytes'),r)) for r in conn.execute(
                'SELECT kind,count(*),sum(pg_column_size(payload)) FROM sig_archive GROUP BY kind ORDER BY kind').fetchall()]
            current=conn.execute("SELECT payload FROM sig_archive WHERE kind='workspace' AND key='current'").fetchone()
            api=conn.execute("SELECT key,payload FROM sig_archive WHERE kind='api_matches' ORDER BY key").fetchall()
            versions=[dict(zip(('saved_at','history','fixtures','research'),r)) for r in conn.execute(
                "SELECT saved_at,jsonb_array_length(COALESCE(payload->'history','[]'::jsonb)),jsonb_array_length(COALESCE(payload->'fixtures','[]'::jsonb)),jsonb_array_length(COALESCE(payload->'research_competitions_40','[]'::jsonb)) FROM sig_archive WHERE kind='workspace_version' ORDER BY saved_at").fetchall()]
            files=conn.execute("SELECT key,payload FROM sig_archive WHERE kind='source_csv' ORDER BY key").fetchall()
            old_workspaces=conn.execute("SELECT key,jsonb_build_object('history',COALESCE(payload->'history','[]'::jsonb),'fixtures',COALESCE(payload->'fixtures','[]'::jsonb),'research_competitions_40',COALESCE(payload->'research_competitions_40','[]'::jsonb)) FROM sig_archive WHERE kind='workspace_version' ORDER BY key").fetchall()
        return dict(inventory=inventory,current=current[0] if current else None,api=api,versions=versions,files=files,old_workspaces=old_workspaces)

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
