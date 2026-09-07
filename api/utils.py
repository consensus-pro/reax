import os
import re
import psycopg2
import resend
import random
import time
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
from flask import g

resend.api_key = os.environ.get("RESEND_API_KEY")

_db_pool = None
_allowed_domains_cache = None

def get_pool():
    global _db_pool
    if _db_pool is None:
        _db_pool = psycopg2.pool.SimpleConnectionPool(
            1,
            20,
            host=os.environ.get("DATA_POSTGRES_HOST"),
            database=os.environ.get("DATA_POSTGRES_DATABASE"),
            user=os.environ.get("DATA_POSTGRES_USER"),
            password=os.environ.get("DATA_POSTGRES_PASSWORD"),
            sslmode="require",
            connect_timeout=5
        )
    return _db_pool

def get_db():
    if 'db_conn' not in g:
        g.db_conn = get_pool().getconn()
    return g.db_conn

def return_db_conn():
    conn = g.pop('db_conn', None)
    if conn is not None:
        get_pool().putconn(conn)

def generate_code():
    return str(random.randint(100000, 999999))

def is_valid_email(email):
    return re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email) is not None

def load_allowed_domains():
    global _allowed_domains_cache
    if _allowed_domains_cache is not None:
        return _allowed_domains_cache
    try:
        import json
        with open(os.path.join(os.path.dirname(__file__), '..', 'TrueEmail.json'), 'r', encoding='utf-8') as f:
            domains = json.load(f)
        _allowed_domains_cache = domains
        return domains
    except FileNotFoundError:
        raise Exception("FILE_NOT_FOUND")
    except json.JSONDecodeError:
        raise Exception("FILE_FORMAT_ERROR")

def is_allowed_email(email):
    domains = load_allowed_domains()
    domain = email.split('@')[-1].lower()
    return domain in domains

def update_page_view(page_path):
    if not page_path or page_path.startswith('/api') or page_path.startswith('/svg') or page_path.startswith('/static') or page_path.startswith('/user'):
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO page_views (page_path, view_count, last_visited)
        VALUES (%s, 1, CURRENT_TIMESTAMP)
        ON CONFLICT (page_path)
        DO UPDATE SET view_count = page_views.view_count + 1, last_visited = CURRENT_TIMESTAMP
    """, (page_path,))
    conn.commit()

def get_page_views():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT page_path, view_count, last_visited FROM page_views ORDER BY view_count DESC")
    rows = cur.fetchall()
    return rows