"""Crash-safe local SQLite progress, no cookies or authentication values stored."""
from __future__ import annotations
import contextlib
import datetime as dt
import json
import os
import sqlite3
import sys
import tempfile
from urllib.parse import quote
from pathlib import Path


def utc_now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def safe_local_path(path: Path) -> Path:
    """Reject links (including ancestor/junction links), hardlinks and long Win10 paths.

    Local same-user concurrent filesystem attackers are outside this portable guard;
    use a private local output directory, not a shared/network writable directory.
    """
    path = Path(os.path.abspath(path))
    if len(str(path)) > 240:
        raise RuntimeError("PATH_TOO_LONG_FOR_WINDOWS_10")
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise RuntimeError("FILESYSTEM_LINK_FORBIDDEN:" + str(part))
        if part.exists():
            st = part.lstat()
            if getattr(st, "st_file_attributes", 0) & 0x400:
                raise RuntimeError("WINDOWS_REPARSE_POINT_FORBIDDEN")
            if part.is_file() and st.st_nlink > 1:
                raise RuntimeError("FILESYSTEM_HARDLINK_FORBIDDEN")
    return path


def atomic_bytes(path: Path, value: bytes) -> None:
    path = safe_local_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name+".tmp-", dir=path.parent)
    tmp = Path(name)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(value); f.flush(); os.fsync(f.fileno())
        safe_local_path(path)
        os.replace(tmp, path)
        if os.name != "nt":
            dir_fd = os.open(path.parent, os.O_RDONLY)
            try: os.fsync(dir_fd)
            finally: os.close(dir_fd)
    finally:
        tmp.unlink(missing_ok=True)


def atomic_json(path: Path, value) -> None:
    atomic_bytes(path,(json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode("utf-8"))


def inspect_existing_db(path):
    if not path.exists():
        return
    if path.stat().st_size == 0 or path.stat().st_size > 64*1024*1024:
        raise RuntimeError("SQLITE_SIZE_OR_EMPTY_FILE_INVALID")
    db = sqlite3.connect("file:"+quote(str(path),safe="/:")+"?mode=ro",uri=True,timeout=5)
    try:
        if db.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
            raise RuntimeError("SQLITE_INTEGRITY_FAILED")
        expected = {
            "pages":{"url","slug","category","status","captured_at","attempts","result_json","error"},
            "discovery":{"url","category","observed_at","method"},
            "assets":{"url","slug","sha256","relative_path","bytes","width","height","status"},
            "events":{"seq","at","kind","detail_json"}}
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name!='sqlite_sequence'")}
        if tables != set(expected) or db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type IN ('trigger','view')").fetchone()[0]:
            raise RuntimeError("UNRELATED_OR_CHANGED_SQLITE_SCHEMA")
        for table, columns in expected.items():
            if {r[1] for r in db.execute(f"PRAGMA table_info({table})")} != columns:
                raise RuntimeError("UNRELATED_OR_CHANGED_SQLITE_COLUMNS")
    finally:
        db.close()


class Store:
    def __init__(self,path:Path):
        path = safe_local_path(path)
        for suffix in ("-wal", "-shm", "-journal"):
            safe_local_path(Path(str(path)+suffix))
        inspect_existing_db(path)
        self.allowed_urls = None
        self.allowed_media_slugs = None
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
        if self.allowed_urls is not None and (url not in self.allowed_urls or slug != url.rstrip("/").split("/")[-1]):
            raise RuntimeError("PAGE_WRITE_OUTSIDE_PILOT_SCOPE")
        payload=json.dumps(data,ensure_ascii=False,sort_keys=True)
        with self.db:
            self.db.execute('''INSERT INTO pages(url,slug,category,status,captured_at,attempts,result_json,error)
              VALUES(?,?,?,?,?,1,?,?)
              ON CONFLICT(url) DO UPDATE SET slug=excluded.slug,category=excluded.category,
              status=excluded.status,captured_at=excluded.captured_at,
              attempts=pages.attempts+1,result_json=excluded.result_json,error=excluded.error''',
              (url,slug,category,status,utc_now(),payload,error))

    def discover(self,url:str,category:str,method:str):
        if self.allowed_urls is not None and url not in self.allowed_urls:
            return
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO discovery(url,category,observed_at,method) VALUES(?,?,?,?)",
                            (url,category,utc_now(),method))

    def urls(self)->list[tuple[str,str]]:
        return list(self.db.execute("SELECT url,MIN(category) FROM discovery GROUP BY url ORDER BY url"))

    def record_asset(self,slug:str,url:str,sha:str,path:str|None,bytes_n:int,width:int,height:int,status:str):
        if self.allowed_media_slugs is not None and slug not in self.allowed_media_slugs:
            raise RuntimeError("ASSET_WRITE_OUTSIDE_PILOT_MEDIA_SCOPE")
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
    path = safe_local_path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with open(path,"a+b") as file:
        file.seek(0);file.write(b"1");file.flush()
        acquired=False
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
            acquired=True
            yield
        finally:
            if acquired and os.name=="nt":
                try: file.seek(0);msvcrt.locking(file.fileno(),msvcrt.LK_UNLCK,1)
                except OSError:pass
            elif acquired:
                try:fcntl.flock(file.fileno(),fcntl.LOCK_UN)
                except OSError:pass
