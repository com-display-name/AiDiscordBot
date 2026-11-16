"""Small async SQLite layer for config, warnings, economy, and levels."""

from __future__ import annotations

import asyncio
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


class Database:
    _CONFIG_FIELDS = frozenset(
        {"modlog_channel_id", "welcome_channel_id", "welcome_message", "autorole_id"}
    )
    _COOLDOWN_FIELDS = frozenset({"last_daily", "last_work", "last_heist"})

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def setup(self) -> None:
        await asyncio.to_thread(self._setup_sync)

    def _setup_sync(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS guild_config (
                    guild_id INTEGER PRIMARY KEY,
                    modlog_channel_id INTEGER,
                    welcome_channel_id INTEGER,
                    welcome_message TEXT,
                    autorole_id INTEGER
                );

                CREATE TABLE IF NOT EXISTS warnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    moderator_id INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_warnings_guild_user
                    ON warnings (guild_id, user_id);

                CREATE TABLE IF NOT EXISTS marriages (
                    user_id INTEGER PRIMARY KEY,
                    partner_id INTEGER NOT NULL,
                    married_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS economy (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER NOT NULL DEFAULT 0,
                    last_daily TEXT,
                    last_work TEXT,
                    last_heist TEXT
                );

                CREATE TABLE IF NOT EXISTS levels (
                    user_id INTEGER PRIMARY KEY,
                    xp INTEGER NOT NULL DEFAULT 0,
                    last_xp TEXT
                );

                CREATE TABLE IF NOT EXISTS scheduled_unmutes (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    role_id INTEGER NOT NULL,
                    unmute_at TEXT NOT NULL,
                    PRIMARY KEY (guild_id, user_id)
                );

                CREATE TABLE IF NOT EXISTS scheduled_unbans (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    unban_at TEXT NOT NULL,
                    PRIMARY KEY (guild_id, user_id)
                );

                CREATE TABLE IF NOT EXISTS reaction_counts (
                    action TEXT NOT NULL,
                    giver_id INTEGER NOT NULL,
                    receiver_id INTEGER NOT NULL,
                    count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (action, giver_id, receiver_id)
                );
                """
            )

    async def ping(self) -> None:
        def work() -> None:
            with self._connection() as conn:
                conn.execute("SELECT 1").fetchone()

        await asyncio.to_thread(work)

    # ---------- Guild config ----------

    async def get_guild_config(self, guild_id: int) -> dict[str, Any]:
        def work() -> dict[str, Any]:
            with self._connection() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)", (guild_id,)
                )
                row = conn.execute(
                    "SELECT * FROM guild_config WHERE guild_id=?", (guild_id,)
                ).fetchone()
            return dict(row)

        return await asyncio.to_thread(work)

    async def set_config(self, guild_id: int, **fields: Any) -> None:
        invalid = set(fields) - self._CONFIG_FIELDS
        if invalid:
            raise ValueError(f"Invalid config field(s): {', '.join(sorted(invalid))}")
        if not fields:
            return

        def work() -> None:
            with self._connection() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)", (guild_id,)
                )
                assignments = ", ".join(f"{name}=?" for name in fields)
                conn.execute(
                    f"UPDATE guild_config SET {assignments} WHERE guild_id=?",
                    (*fields.values(), guild_id),
                )

        await asyncio.to_thread(work)

    # ---------- Warnings ----------

    async def add_warning(
        self,
        guild_id: int,
        user_id: int,
        moderator_id: int,
        reason: str,
        created_at: str,
    ) -> int:
        def work() -> int:
            with self._connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO warnings (guild_id, user_id, moderator_id, reason, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (guild_id, user_id, moderator_id, reason, created_at),
                )
                warning_id = cursor.lastrowid
            return int(warning_id)

        return await asyncio.to_thread(work)

    async def get_warnings(
        self, guild_id: int, user_id: int, limit: int = 10
    ) -> list[dict[str, Any]]:
        def work() -> list[dict[str, Any]]:
            with self._connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM warnings
                    WHERE guild_id=? AND user_id=?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (guild_id, user_id, limit),
                ).fetchall()
            return [dict(row) for row in rows]

        return await asyncio.to_thread(work)

    async def count_warnings(self, guild_id: int, user_id: int) -> int:
        def work() -> int:
            with self._connection() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) AS count FROM warnings WHERE guild_id=? AND user_id=?",
                    (guild_id, user_id),
                ).fetchone()
            return int(row["count"])

        return await asyncio.to_thread(work)

    async def delete_warning(self, guild_id: int, user_id: int, warning_id: int) -> bool:
        def work() -> bool:
            with self._connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM warnings WHERE id=? AND guild_id=? AND user_id=?",
                    (warning_id, guild_id, user_id),
                )
                return cursor.rowcount > 0

        return await asyncio.to_thread(work)

    async def clear_warnings(self, guild_id: int, user_id: int) -> int:
        def work() -> int:
            with self._connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM warnings WHERE guild_id=? AND user_id=?",
                    (guild_id, user_id),
                )
                return cursor.rowcount

        return await asyncio.to_thread(work)

    # ---------- Reactions ----------

    async def increment_reaction_count(
        self, action: str, user1_id: int, user2_id: int
    ) -> int:
        # Store as an unordered pair so "back" responses share/increment the same counter.
        a, b = sorted((user1_id, user2_id))
        def work() -> int:
            with self._connection() as conn:
                conn.execute(
                    """
                    INSERT INTO reaction_counts (action, giver_id, receiver_id, count)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(action, giver_id, receiver_id) DO UPDATE SET
                        count = count + 1
                    """,
                    (action, a, b),
                )
                row = conn.execute(
                    "SELECT count FROM reaction_counts WHERE action=? AND giver_id=? AND receiver_id=?",
                    (action, a, b),
                ).fetchone()
            return int(row["count"])

        return await asyncio.to_thread(work)

    # ---------- Marriages ----------

    async def get_marriage(self, user_id: int) -> dict[str, Any] | None:
        def work() -> dict[str, Any] | None:
            with self._connection() as conn:
                row = conn.execute(
                    "SELECT * FROM marriages WHERE user_id=?", (user_id,)
                ).fetchone()
            return dict(row) if row is not None else None

        return await asyncio.to_thread(work)

    async def marry(self, first_id: int, second_id: int, married_at: str) -> bool:
        def work() -> bool:
            try:
                with self._connection() as conn:
                    existing = conn.execute(
                        "SELECT user_id FROM marriages WHERE user_id IN (?, ?)",
                        (first_id, second_id),
                    ).fetchall()
                    if existing:
                        return False
                    conn.execute(
                        "INSERT INTO marriages (user_id, partner_id, married_at) VALUES (?, ?, ?)",
                        (first_id, second_id, married_at),
                    )
                    conn.execute(
                        "INSERT INTO marriages (user_id, partner_id, married_at) VALUES (?, ?, ?)",
                        (second_id, first_id, married_at),
                    )
                return True
            except sqlite3.IntegrityError:
                return False

        return await asyncio.to_thread(work)

    async def divorce(self, user_id: int) -> int | None:
        def work() -> int | None:
            with self._connection() as conn:
                row = conn.execute(
                    "SELECT partner_id FROM marriages WHERE user_id=?", (user_id,)
                ).fetchone()
                if row is None:
                    return None
                partner_id = int(row["partner_id"])
                conn.execute(
                    "DELETE FROM marriages WHERE user_id IN (?, ?)",
                    (user_id, partner_id),
                )
            return partner_id

        return await asyncio.to_thread(work)

    # ---------- Economy ----------

    @staticmethod
    def _ensure_economy(conn: sqlite3.Connection, user_id: int) -> None:
        conn.execute("INSERT OR IGNORE INTO economy (user_id) VALUES (?)", (user_id,))

    async def get_economy(self, user_id: int) -> dict[str, Any]:
        def work() -> dict[str, Any]:
            with self._connection() as conn:
                self._ensure_economy(conn, user_id)
                row = conn.execute(
                    "SELECT * FROM economy WHERE user_id=?", (user_id,)
                ).fetchone()
            return dict(row)

        return await asyncio.to_thread(work)

    async def get_balance(self, user_id: int) -> int:
        row = await self.get_economy(user_id)
        return int(row["balance"])

    async def add_balance(self, user_id: int, amount: int) -> int:
        def work() -> int:
            with self._connection() as conn:
                self._ensure_economy(conn, user_id)
                conn.execute(
                    "UPDATE economy SET balance = balance + ? WHERE user_id=?",
                    (amount, user_id),
                )
                row = conn.execute(
                    "SELECT balance FROM economy WHERE user_id=?", (user_id,)
                ).fetchone()
            return int(row["balance"])

        return await asyncio.to_thread(work)

    async def settle_bet(self, user_id: int, bet: int, payout: int) -> int | None:
        """Deduct a bet and add a payout in one transaction. Returns new balance."""

        def work() -> int | None:
            with self._connection() as conn:
                self._ensure_economy(conn, user_id)
                row = conn.execute(
                    "SELECT balance FROM economy WHERE user_id=?", (user_id,)
                ).fetchone()
                balance = int(row["balance"])
                if balance < bet:
                    return None
                new_balance = balance - bet + payout
                conn.execute(
                    "UPDATE economy SET balance=? WHERE user_id=?",
                    (new_balance, user_id),
                )
            return new_balance

        return await asyncio.to_thread(work)

    async def transfer(self, from_id: int, to_id: int, amount: int) -> bool:
        def work() -> bool:
            with self._connection() as conn:
                self._ensure_economy(conn, from_id)
                self._ensure_economy(conn, to_id)
                row = conn.execute(
                    "SELECT balance FROM economy WHERE user_id=?", (from_id,)
                ).fetchone()
                if int(row["balance"]) < amount:
                    return False
                conn.execute(
                    "UPDATE economy SET balance = balance - ? WHERE user_id=?",
                    (amount, from_id),
                )
                conn.execute(
                    "UPDATE economy SET balance = balance + ? WHERE user_id=?",
                    (amount, to_id),
                )
                return True

        return await asyncio.to_thread(work)

    async def set_cooldown(self, user_id: int, field: str, timestamp: str) -> None:
        if field not in self._COOLDOWN_FIELDS:
            raise ValueError(f"Invalid cooldown field: {field}")

        def work() -> None:
            with self._connection() as conn:
                self._ensure_economy(conn, user_id)
                conn.execute(
                    f"UPDATE economy SET {field}=? WHERE user_id=?", (timestamp, user_id)
                )

        await asyncio.to_thread(work)

    async def economy_top(self, limit: int = 10) -> list[dict[str, Any]]:
        def work() -> list[dict[str, Any]]:
            with self._connection() as conn:
                rows = conn.execute(
                    """
                    SELECT user_id, balance FROM economy
                    WHERE balance > 0
                    ORDER BY balance DESC, user_id ASC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            return [dict(row) for row in rows]

        return await asyncio.to_thread(work)

    # ---------- Levels ----------

    @staticmethod
    def _ensure_level(conn: sqlite3.Connection, user_id: int) -> None:
        conn.execute("INSERT OR IGNORE INTO levels (user_id) VALUES (?)", (user_id,))

    async def get_level(self, user_id: int) -> dict[str, Any]:
        def work() -> dict[str, Any]:
            with self._connection() as conn:
                self._ensure_level(conn, user_id)
                row = conn.execute(
                    "SELECT * FROM levels WHERE user_id=?", (user_id,)
                ).fetchone()
            return dict(row)

        return await asyncio.to_thread(work)

    async def award_xp(
        self,
        user_id: int,
        amount: int,
        now_iso: str,
        cooldown_seconds: int,
    ) -> tuple[int, int] | None:
        """Add XP if the cooldown has elapsed. Returns (old_xp, new_xp)."""

        def work() -> tuple[int, int] | None:
            with self._connection() as conn:
                self._ensure_level(conn, user_id)
                row = conn.execute(
                    "SELECT xp, last_xp FROM levels WHERE user_id=?", (user_id,)
                ).fetchone()
                now = _parse_dt(now_iso) or datetime.now(timezone.utc)
                last = _parse_dt(row["last_xp"])
                if last is not None and (now - last).total_seconds() < cooldown_seconds:
                    return None
                old_xp = int(row["xp"])
                new_xp = old_xp + amount
                conn.execute(
                    "UPDATE levels SET xp=?, last_xp=? WHERE user_id=?",
                    (new_xp, now_iso, user_id),
                )
            return old_xp, new_xp

        return await asyncio.to_thread(work)

    async def level_rank(self, user_id: int) -> int:
        def work() -> int:
            with self._connection() as conn:
                self._ensure_level(conn, user_id)
                row = conn.execute(
                    "SELECT xp FROM levels WHERE user_id=?", (user_id,)
                ).fetchone()
                ahead = conn.execute(
                    "SELECT COUNT(*) AS count FROM levels WHERE xp > ?", (row["xp"],)
                ).fetchone()
            return int(ahead["count"]) + 1

        return await asyncio.to_thread(work)

    async def level_user_count(self) -> int:
        def work() -> int:
            with self._connection() as conn:
                row = conn.execute("SELECT COUNT(*) AS count FROM levels").fetchone()
            return int(row["count"])

        return await asyncio.to_thread(work)

    async def level_top(self, limit: int = 10) -> list[dict[str, Any]]:
        def work() -> list[dict[str, Any]]:
            with self._connection() as conn:
                rows = conn.execute(
                    """
                    SELECT user_id, xp FROM levels
                    WHERE xp > 0
                    ORDER BY xp DESC, user_id ASC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            return [dict(row) for row in rows]

        return await asyncio.to_thread(work)

    # ---------- Scheduled moderation ----------

    async def add_scheduled_unmute(
        self, guild_id: int, user_id: int, role_id: int, unmute_at: str
    ) -> None:
        def work() -> None:
            with self._connection() as conn:
                conn.execute(
                    """
                    INSERT INTO scheduled_unmutes (guild_id, user_id, role_id, unmute_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(guild_id, user_id) DO UPDATE SET
                        role_id=excluded.role_id,
                        unmute_at=excluded.unmute_at
                    """,
                    (guild_id, user_id, role_id, unmute_at),
                )

        await asyncio.to_thread(work)

    async def remove_scheduled_unmute(self, guild_id: int, user_id: int) -> None:
        def work() -> None:
            with self._connection() as conn:
                conn.execute(
                    "DELETE FROM scheduled_unmutes WHERE guild_id=? AND user_id=?",
                    (guild_id, user_id),
                )

        await asyncio.to_thread(work)

    async def get_due_scheduled_unmutes(self, now_iso: str) -> list[dict[str, Any]]:
        def work() -> list[dict[str, Any]]:
            with self._connection() as conn:
                rows = conn.execute(
                    """
                    SELECT guild_id, user_id, role_id, unmute_at
                    FROM scheduled_unmutes
                    WHERE unmute_at <= ?
                    ORDER BY unmute_at ASC
                    """,
                    (now_iso,),
                ).fetchall()
            return [dict(row) for row in rows]

        return await asyncio.to_thread(work)

    async def add_scheduled_unban(
        self, guild_id: int, user_id: int, unban_at: str
    ) -> None:
        def work() -> None:
            with self._connection() as conn:
                conn.execute(
                    """
                    INSERT INTO scheduled_unbans (guild_id, user_id, unban_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(guild_id, user_id) DO UPDATE SET
                        unban_at=excluded.unban_at
                    """,
                    (guild_id, user_id, unban_at),
                )

        await asyncio.to_thread(work)

    async def remove_scheduled_unban(self, guild_id: int, user_id: int) -> None:
        def work() -> None:
            with self._connection() as conn:
                conn.execute(
                    "DELETE FROM scheduled_unbans WHERE guild_id=? AND user_id=?",
                    (guild_id, user_id),
                )

        await asyncio.to_thread(work)

    async def get_due_scheduled_unbans(self, now_iso: str) -> list[dict[str, Any]]:
        def work() -> list[dict[str, Any]]:
            with self._connection() as conn:
                rows = conn.execute(
                    """
                    SELECT guild_id, user_id, unban_at
                    FROM scheduled_unbans
                    WHERE unban_at <= ?
                    ORDER BY unban_at ASC
                    """,
                    (now_iso,),
                ).fetchall()
            return [dict(row) for row in rows]

        return await asyncio.to_thread(work)
