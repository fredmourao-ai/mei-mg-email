import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / '.env')
with psycopg.connect(os.environ['DATABASE_URL'], connect_timeout=5) as c:
    with c.cursor() as cur:
        cur.execute("set statement_timeout='5s'")
        cur.execute("select indexname, indexdef from pg_indexes where schemaname='mei_email' and tablename in ('empresas','envios') order by tablename,indexname")
        for name, definition in cur.fetchall():
            print(name, definition)
