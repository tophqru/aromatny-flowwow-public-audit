"""Crash-safe local SQLite progress, no cookies or authentication values stored."""
from __future__ import annotations
import contextlib
import datetime as dt
import json
import os
import sqlite3
import sys
from pathlib import Path


def utc_now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def atomic_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+".tmp-"+str(os.getpid()))
    try:
        with open(tmp,"wb") as f:
            f.write(value); f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
        # Persist the directory entry on POSIX. Windows has no portable directory
        # fsync; the file flush + atomic replacement is the available guarantee.
        if os.name != "nt":
            dir_fd=os.open(path.parent,os.O_RDONLY)
            try:os.fsync(dir_fd)
            finally:os.close(dir_fd)
    finally:
        tmp.unlink(missing_ok=True)


def atomic_json(path: Path, value) -> None:
    atomic_bytes(path,(json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode("utf-8"))


class Store:
    def __init__(self,path:Path):
        self.path=path
        path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(path,timeout=20,isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=20000")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS pages(
          url TEXT PRIMARY KEY, slug TEXT NOT NULL, category TEXT,
          status TEXT NOT NULL, captured_at TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 1,
          result_json TEXT NOT NULL, error TEXT);
        CREATE TABLE IF NOT EXISTS discovery(
          url TEXT NOT NULL, category TEXT NOT NULL, observed_at TEXT NOT NULL,
          method TEXT NOT NULL, PRIMARY KEY(url,category));
        CREATE TABLE IF NOT EXISTS assets(
          url TEXT NOT NULL, slug TEXT NOT NULL, sha256 TEXT NOT NULL,
          relative_path TEXT, bytes INTEGER NOT NULL, width INTEGER NOT NULL,
          height INTEGER NOT NULL, status TEXT NOT NULL,
          PRIMARY KEY(url,slug));
        CREATE TABLE IF NOT EXISTS events(
          seq INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL,
          kind TEXT NOT NULL, detail_json TEXT NOT NULL);
        ''')

    def close(self): self.db.close()

    def event(self,kind:str,data:dict):
        self.db.execute("INSERT INTO events(at,kind,detail_json) VALUES(?,?,?)",
                        (utc_now(),kind,json.dumps(data,ensure_ascii=False,sort_keys=True)))

    def seen(self,url:str) -> bool:
        r=self.db.execute("SELECT status FROM pages WHERE url=?",(url,)).fetchone()
        # Blocked/interrupted/ambiguous pages can be retried with --retry-failed.
        return bool(r and r[0]=="CAPTURED")

    def record_page(self,url:str,slug:str,category:str,status:str,data:dict,error:str|None=None):
        payload=json.dumps(data,ensure_ascii=False,sort_keys=True)
        with self.db:
            self.db.execute('''INSERT INTO pages(url,slug,category,status,captured_at,attempts,result_json,error)
              VALUES(?,?,?,?,?,1,?,?)
              ON CONFLICT(url) DO UPDATE SET slug=excluded.slug,category=excluded.category,
              status=excluded.status,captured_at=excluded.captured_at,
              attempts=pages.attempts+1,result_json=excluded.result_json,error=excluded.error''',
              (url,slug,category,status,utc_now(),payload,error))

    def discover(self,url:str,category:str,method:str):
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO discovery(url,category,observed_at,method) VALUES(?,?,?,?)",
                            (url,category,utc_now(),method))

    def urls(self)->list[tuple[str,str]]:
        return list(self.db.execute("SELECT url,MIN(category) FROM discovery GROUP BY url ORDER BY url"))

    def record_asset(self,slug:str,url:str,sha:str,path:str|None,bytes_n:int,width:int,height:int,status:str):
        with self.db:
            self.db.execute('''INSERT INTO assets(url,slug,sha256,relative_path,bytes,width,height,status)
              VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(url,slug) DO UPDATE SET
              sha256=excluded.sha256,relative_path=excluded.relative_path,bytes=excluded.bytes,
              width=excluded.width,height=excluded.height,status=excluded.status''',
              (url,slug,sha,path,bytes_n,width,height,status))

    def existing_asset(self,slug:str,url:str):
        return self.db.execute("SELECT sha256,relative_path,bytes,status FROM assets WHERE slug=? AND url=?",(slug,url)).fetchone()

    def page_rows(self):
        return self.db.execute("SELECT url,slug,category,status,captured_at,result_json,error,attempts FROM pages ORDER BY slug").fetchall()

    def asset_rows(self):
        return self.db.execute("SELECT url,slug,sha256,relative_path,bytes,width,height,status FROM assets ORDER BY slug,url").fetchall()

    def event_rows(self):
        return self.db.execute("SELECT seq,at,kind,detail_json FROM events ORDER BY seq").fetchall()


@contextlib.contextmanager
def exclusive_run_lock(path:Path):
    """OS-released exclusive file lock, including after power loss / process crash."""
    path.parent.mkdir(parents=True,exist_ok=True)
    with open(path,"a+b") as file:
        file.seek(0);file.write(b"1");file.flush()
        try:
            if os.name=="nt":
                import msvcrt
                file.seek(0)
                try: msvcrt.locking(file.fileno(),msvcrt.LK_NBLCK,1)
                except OSError as e: raise RuntimeError("Another capture process is using this folder") from e
            else:
                import fcntl
                try:fcntl.flock(file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
                except OSError as e:raise RuntimeError("Another capture process is using this folder") from e
            yield
        finally:
            if os.name=="nt":
                try: file.seek(0);msvcrt.locking(file.fileno(),msvcrt.LK_UNLCK,1)
                except OSError:pass
            else:
                try:fcntl.flock(file.fileno(),fcntl.LOCK_UN)
                except OSError:pass
