"""Open a stable Cursor database without writing SQLite read marks or copying the source."""
from contextlib import closing, contextmanager
from pathlib import Path
import sqlite3


def signature(path):
    try:
        st = path.stat()
    except FileNotFoundError:
        return None
    return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns


@contextmanager
def cursor_db(path):
    path = path.resolve()
    wal, shm = (Path(str(path) + s) for s in ("-wal", "-shm"))
    before = tuple(signature(p) for p in (path, wal))
    if not before[0] or bool(before[1]) != shm.exists():
        raise sqlite3.DatabaseError("missing database or incomplete WAL sidecars")
    live = before[1] and before[1][2] > 0
    # The normal read-only WAL connection writes a read mark in -shm. Exclusive
    # locking mode keeps the WAL index in process memory. unix-none performs no
    # OS lock writes; reject a racing writer by checking the original generation.
    query = "?mode=ro&vfs=unix-none" if live else "?mode=ro&immutable=1"
    with closing(sqlite3.connect(path.as_uri() + query, uri=True)) as db:
        if live and db.execute("PRAGMA locking_mode=EXCLUSIVE").fetchone() != ("exclusive",):
            raise sqlite3.DatabaseError("private WAL index unavailable")
        db.execute("PRAGMA query_only=ON")
        yield db
        if before != tuple(signature(p) for p in (path, wal)):
            raise sqlite3.DatabaseError("database changed during read")
