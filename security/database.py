#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fluent Media Player - Protected Local SQLite History Database
Cung cấp lưu trữ lịch sử xem phim an toàn thay thế JSON ghi đè trực tiếp:
- SQLite WAL (Write-Ahead Logging) + synchronous=FULL chống mất dữ liệu khi tắt nguồn đột ngột
- Transaction ACID (BEGIN IMMEDIATE / COMMIT / ROLLBACK)
- Tự động kiểm tra toàn vẹn (PRAGMA integrity_check)
- Sao lưu định kỳ kèm SHA-256 sidecar & tự động khôi phục khi phát hiện DB lỗi
- Tự động di trú dữ liệu từ video_history.json cũ sang SQLite một lần duy nhất
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime


SCHEMA_VERSION = "1"


def _file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _norm_key(file_path: str) -> str:
    return os.path.normcase(os.path.abspath(file_path))


def verify_database_integrity(db_path: str) -> tuple[bool, str]:
    """
    Kiểm tra tính toàn vẹn cấu trúc B-Tree của SQLite (PRAGMA integrity_check)
    và kiểm tra hợp lệ các bảng dữ liệu cốt lõi.
    """
    if not os.path.isfile(db_path) or os.path.getsize(db_path) == 0:
        return False, "Tệp database không tồn tại hoặc có kích thước 0 byte."

    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=3.0)
        cur = conn.cursor()
        rows = cur.execute("PRAGMA integrity_check;").fetchall()
        if not rows or len(rows) != 1 or str(rows[0][0]).lower() != "ok":
            return False, f"PRAGMA integrity_check thất bại: {rows}"

        tables = {
            r[0]
            for r in cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table';"
            ).fetchall()
        }
        if "watch_history" not in tables or "schema_meta" not in tables:
            return False, "Thiếu bảng schema_meta hoặc watch_history trong database."

        for norm_path, file_path, pos, pct, updated_at in cur.execute(
            "SELECT norm_path, file_path, pos, pct, updated_at FROM watch_history;"
        ):
            if not isinstance(norm_path, str) or not norm_path:
                return False, "Dữ liệu norm_path không hợp lệ."
            if not isinstance(file_path, str) or not file_path:
                return False, "Dữ liệu file_path không hợp lệ."
            if not (isinstance(pos, (int, float)) and math.isfinite(pos) and pos >= 0):
                return False, "Dữ liệu vị trí phát (pos) bị hỏng."
            if not (isinstance(pct, (int, float)) and math.isfinite(pct) and 0 <= pct <= 100):
                return False, "Dữ liệu phần trăm (pct) bị hỏng."
            if not (isinstance(updated_at, (int, float)) and math.isfinite(updated_at)):
                return False, "Dữ liệu thời gian cập nhật bị hỏng."

        return True, "ok"
    except sqlite3.DatabaseError as exc:
        return False, f"Lỗi cấu trúc SQLite: {exc}"
    except Exception as exc:
        return False, f"Không thể kiểm tra database: {exc}"
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


class HistoryDatabase:
    """
    Quản lý lịch sử xem video bằng SQLite ACID + Backup & Recovery tự động.
    """

    def __init__(
        self,
        db_path: str,
        backup_dir: str,
        legacy_json_path: str | None = None,
        max_backups: int = 5,
    ):
        self.db_path = os.path.abspath(db_path)
        self.backup_dir = os.path.abspath(backup_dir)
        self.legacy_json_path = os.path.abspath(legacy_json_path) if legacy_json_path else None
        self.max_backups = max(1, int(max_backups))

        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None
        self._in_tx = False
        self.last_recovery_event: str | None = None

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)

        self._initialize()

    def _open_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.db_path,
            timeout=5.0,
            isolation_level=None,  # Tự kiểm soát BEGIN IMMEDIATE / COMMIT / ROLLBACK
            check_same_thread=False,
        )
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=FULL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _ensure_schema(self, conn: sqlite3.Connection):
        conn.execute("BEGIN IMMEDIATE;")
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS watch_history (
                    norm_path TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    pos REAL NOT NULL CHECK(pos >= 0),
                    pct REAL NOT NULL CHECK(pct >= 0 AND pct <= 100),
                    updated_at REAL NOT NULL
                );
                """
            )
            conn.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('schema_version', ?);",
                (SCHEMA_VERSION,),
            )
            conn.execute("COMMIT;")
        except Exception:
            conn.execute("ROLLBACK;")
            raise

    def _close_conn(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
            self._in_tx = False

    def _quarantine_corrupt_db(self, suffix: str | None = None):
        ts = suffix or datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        for ext in ("", "-wal", "-shm", "-journal"):
            src = self.db_path + ext
            if os.path.exists(src):
                dst = f"{self.db_path}.corrupt.{ts}{ext}"
                try:
                    shutil.move(src, dst)
                except Exception:
                    try:
                        os.remove(src)
                    except Exception:
                        pass

    def _initialize(self):
        with self._lock:
            db_existed = os.path.exists(self.db_path)
            if db_existed:
                ok, reason = verify_database_integrity(self.db_path)
                if not ok:
                    restored, msg = self.recover_from_backup(reason=reason)
                    if restored:
                        self.last_recovery_event = f"restored: {msg}"
                    else:
                        self.last_recovery_event = f"fresh_reset: {msg}"

            self._conn = self._open_connection()
            self._ensure_schema(self._conn)

            # Di trú một lần từ video_history.json nếu bảng đang rỗng
            row_count = self._conn.execute("SELECT COUNT(*) FROM watch_history;").fetchone()[0]
            if row_count == 0 and self.legacy_json_path and os.path.isfile(self.legacy_json_path):
                self._migrate_legacy_json()
            elif row_count > 0 and not self._list_backups():
                self.create_backup()

    def _migrate_legacy_json(self):
        if not self.legacy_json_path or not os.path.isfile(self.legacy_json_path):
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        try:
            with open(self.legacy_json_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, dict):
                raise ValueError("Dữ liệu JSON lịch sử không phải dạng dictionary.")
        except Exception:
            try:
                shutil.move(self.legacy_json_path, f"{self.legacy_json_path}.corrupt.{ts}")
            except Exception:
                pass
            return

        now_base = time.time() - max(len(raw), 1)
        valid_rows: list[tuple[str, str, float, float, float]] = []
        for idx, (path_key, info) in enumerate(raw.items()):
            if not isinstance(path_key, str) or not path_key.strip() or not isinstance(info, dict):
                continue
            try:
                pos = float(info.get("pos", 0.0))
                pct = float(info.get("pct", 0.0))
            except (TypeError, ValueError):
                continue
            if not (math.isfinite(pos) and math.isfinite(pct)):
                continue
            pos = max(0.0, pos)
            pct = max(0.0, min(100.0, pct))
            abs_p = os.path.abspath(path_key)
            valid_rows.append((_norm_key(abs_p), abs_p, pos, pct, now_base + idx * 0.001))

        if valid_rows:
            with self.transaction():
                assert self._conn is not None
                for row in valid_rows:
                    self._conn.execute(
                        """
                        INSERT OR REPLACE INTO watch_history(norm_path, file_path, pos, pct, updated_at)
                        VALUES (?, ?, ?, ?, ?);
                        """,
                        row,
                    )
            self.create_backup()

        try:
            shutil.move(self.legacy_json_path, f"{self.legacy_json_path}.migrated.bak")
        except Exception:
            pass

    @contextmanager
    def transaction(self):
        """Context manager đảm bảo tính nguyên tử BEGIN IMMEDIATE / COMMIT / ROLLBACK."""
        with self._lock:
            if self._conn is None:
                self._conn = self._open_connection()
            if self._in_tx:
                yield self._conn
                return

            self._in_tx = True
            self._conn.execute("BEGIN IMMEDIATE;")
            try:
                yield self._conn
                self._conn.execute("COMMIT;")
            except Exception:
                try:
                    self._conn.execute("ROLLBACK;")
                except Exception:
                    pass
                raise
            finally:
                self._in_tx = False

    def load_all(self) -> dict[str, dict]:
        """Tải toàn bộ lịch sử xem dưới dạng {file_path: {'pos': float, 'pct': float}}."""
        with self._lock:
            if self._conn is None:
                self._conn = self._open_connection()
            rows = self._conn.execute(
                "SELECT file_path, pos, pct FROM watch_history ORDER BY updated_at ASC, rowid ASC;"
            ).fetchall()
            out: dict[str, dict] = {}
            for file_path, pos, pct in rows:
                out[file_path] = {"pos": float(pos), "pct": float(pct)}
            return out

    def upsert_progress(self, file_path: str, pos: float, pct: float) -> None:
        if not isinstance(file_path, str) or not file_path.strip():
            return
        pos_f = max(0.0, float(pos)) if math.isfinite(float(pos)) else 0.0
        pct_f = max(0.0, min(100.0, float(pct))) if math.isfinite(float(pct)) else 0.0
        abs_p = os.path.abspath(file_path)
        norm_p = _norm_key(abs_p)
        now = time.time()

        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO watch_history(norm_path, file_path, pos, pct, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(norm_path) DO UPDATE SET
                    file_path = excluded.file_path,
                    pos = excluded.pos,
                    pct = excluded.pct,
                    updated_at = excluded.updated_at;
                """,
                (norm_p, abs_p, pos_f, pct_f, now),
            )

    def sync_save_all(self, history_data: dict) -> None:
        """
        Đồng bộ toàn bộ dictionary lịch sử vào database trong một transaction nguyên tử duy nhất.
        """
        if not isinstance(history_data, dict):
            return
        now = time.time()
        normalized_items: list[tuple[str, str, float, float, float]] = []
        base_ts = now - max(len(history_data), 1) * 0.001

        for idx, (raw_path, info) in enumerate(history_data.items()):
            if not isinstance(raw_path, str) or not raw_path.strip() or not isinstance(info, dict):
                continue
            try:
                pos = float(info.get("pos", 0.0))
                pct = float(info.get("pct", 0.0))
            except (TypeError, ValueError):
                continue
            if not (math.isfinite(pos) and math.isfinite(pct)):
                continue
            abs_p = os.path.abspath(raw_path)
            normalized_items.append(
                (
                    _norm_key(abs_p),
                    abs_p,
                    max(0.0, pos),
                    max(0.0, min(100.0, pct)),
                    base_ts + idx * 0.001,
                )
            )

        with self.transaction() as conn:
            existing_keys = {
                r[0] for r in conn.execute("SELECT norm_path FROM watch_history;").fetchall()
            }
            new_keys = {item[0] for item in normalized_items}
            removed_keys = existing_keys - new_keys
            for rk in removed_keys:
                conn.execute("DELETE FROM watch_history WHERE norm_path = ?;", (rk,))

            for norm_p, abs_p, pos, pct, ts in normalized_items:
                conn.execute(
                    """
                    INSERT INTO watch_history(norm_path, file_path, pos, pct, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(norm_path) DO UPDATE SET
                        file_path = excluded.file_path,
                        pos = excluded.pos,
                        pct = excluded.pct,
                        updated_at = excluded.updated_at;
                    """,
                    (norm_p, abs_p, pos, pct, ts),
                )

    def rename_entry(self, old_path: str, new_path: str) -> None:
        if not old_path or not new_path:
            return
        old_abs = os.path.abspath(old_path)
        new_abs = os.path.abspath(new_path)
        old_norm = _norm_key(old_abs)
        new_norm = _norm_key(new_abs)

        with self.transaction() as conn:
            row = conn.execute(
                "SELECT pos, pct FROM watch_history WHERE norm_path = ?;",
                (old_norm,),
            ).fetchone()
            if row is not None:
                pos, pct = row
                conn.execute("DELETE FROM watch_history WHERE norm_path = ?;", (old_norm,))
                conn.execute(
                    """
                    INSERT OR REPLACE INTO watch_history(norm_path, file_path, pos, pct, updated_at)
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    (new_norm, new_abs, float(pos), float(pct), time.time()),
                )

    def delete_entry(self, file_path: str) -> None:
        if not file_path:
            return
        norm_p = _norm_key(file_path)
        with self.transaction() as conn:
            conn.execute("DELETE FROM watch_history WHERE norm_path = ?;", (norm_p,))

    def reconcile_missing_files(self) -> list[str]:
        """Xóa các bản ghi lịch sử có tệp video đã bị xóa khỏi ổ đĩa ngoài ứng dụng."""
        removed: list[str] = []
        with self.transaction() as conn:
            rows = conn.execute("SELECT norm_path, file_path FROM watch_history;").fetchall()
            for norm_p, file_p in rows:
                if not os.path.exists(file_p):
                    conn.execute("DELETE FROM watch_history WHERE norm_path = ?;", (norm_p,))
                    removed.append(file_p)
        return removed

    def _list_backups(self) -> list[str]:
        if not os.path.isdir(self.backup_dir):
            return []
        files = [
            os.path.join(self.backup_dir, f)
            for f in os.listdir(self.backup_dir)
            if f.startswith("library_") and f.endswith(".db")
        ]
        files.sort(reverse=True)
        return files

    def create_backup(self) -> str | None:
        """Tạo bản sao lưu nguyên tử qua sqlite3.Connection.backup() kèm mã kiểm tra SHA-256."""
        with self._lock:
            if self._conn is None:
                return None
            os.makedirs(self.backup_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            tmp_bak = os.path.join(self.backup_dir, f".tmp_library_{ts}.db")
            final_bak = os.path.join(self.backup_dir, f"library_{ts}.db")
            sha_path = final_bak + ".sha256"

            dst_conn = None
            try:
                self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                dst_conn = sqlite3.connect(tmp_bak, timeout=5.0)
                self._conn.backup(dst_conn)
                dst_conn.close()
                dst_conn = None

                ok, _ = verify_database_integrity(tmp_bak)
                if not ok:
                    if os.path.exists(tmp_bak):
                        os.remove(tmp_bak)
                    return None

                digest = _file_sha256(tmp_bak)
                tmp_sha = sha_path + ".tmp"
                with open(tmp_sha, "w", encoding="utf-8") as sf:
                    sf.write(digest)
                os.replace(tmp_bak, final_bak)
                os.replace(tmp_sha, sha_path)

                backups = self._list_backups()
                for stale in backups[self.max_backups:]:
                    for p in (stale, stale + ".sha256"):
                        if os.path.exists(p):
                            try:
                                os.remove(p)
                            except OSError:
                                pass
                return final_bak
            except Exception:
                if dst_conn is not None:
                    try:
                        dst_conn.close()
                    except Exception:
                        pass
                for p in (tmp_bak, sha_path + ".tmp"):
                    if os.path.exists(p):
                        try:
                            os.remove(p)
                        except OSError:
                            pass
                return None

    def recover_from_backup(self, reason: str = "") -> tuple[bool, str]:
        """
        Cách ly database lỗi sang *.corrupt.* và phục hồi từ bản sao lưu hợp lệ mới nhất.
        Nếu mọi bản sao lưu đều lỗi hoặc không tồn tại, tạo database mới an toàn (không crash).
        """
        with self._lock:
            self._close_conn()
            self._quarantine_corrupt_db()

            for bak in self._list_backups():
                sha_sidecar = bak + ".sha256"
                if os.path.isfile(sha_sidecar):
                    try:
                        with open(sha_sidecar, "r", encoding="utf-8") as f:
                            expected_hash = f.read().strip().lower()
                        actual_hash = _file_sha256(bak).lower()
                        if not expected_hash or actual_hash != expected_hash:
                            continue
                    except Exception:
                        continue

                ok, _ = verify_database_integrity(bak)
                if not ok:
                    continue

                tmp_restore = f"{self.db_path}.restore.tmp"
                try:
                    shutil.copy2(bak, tmp_restore)
                    ok_restored, _ = verify_database_integrity(tmp_restore)
                    if ok_restored:
                        os.replace(tmp_restore, self.db_path)
                        return True, f"Khôi phục từ backup {os.path.basename(bak)}"
                except Exception:
                    if os.path.exists(tmp_restore):
                        try:
                            os.remove(tmp_restore)
                        except OSError:
                            pass

            return False, (
                f"Không có backup hợp lệ khả dụng (nguyên nhân DB lỗi: {reason or 'unknown'}). "
                "Đã khởi tạo database mới sạch."
            )

    def close(self, create_final_backup: bool = True):
        with self._lock:
            if self._conn is not None:
                if create_final_backup:
                    self.create_backup()
                self._close_conn()
