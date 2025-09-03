
import os
import sqlite3
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, 'career.db')
SCHEMA_FILE = os.path.join(BASE_DIR, 'schema.sql')

@contextmanager
def connect():
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()

def init_db():
    with connect() as con:
        with open(SCHEMA_FILE, 'r', encoding='utf-8') as f:
            con.executescript(f.read())

# Helpers

def query_one(sql, params=()):
    with connect() as con:
        cur = con.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None

def query_all(sql, params=()):
    with connect() as con:
        cur = con.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]

def execute(sql, params=()):
    with connect() as con:
        cur = con.execute(sql, params)
        return cur.lastrowid
