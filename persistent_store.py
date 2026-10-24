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

