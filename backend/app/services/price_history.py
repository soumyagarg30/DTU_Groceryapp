"""Bounded, local observation history. No background provider requests."""
import hashlib
import math
import sqlite3
from pathlib import Path
from ..models.search import PriceObservation, SearchResponse
from .normalization import normalize_query


class PriceHistory:
    def __init__(self, path: str | Path):
        self.path = path

    def enrich(self, response: SearchResponse) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS observations (key TEXT, at TEXT, price REAL, PRIMARY KEY(key, at))')
            for result in response.results:
                for listing in (result.blinkit, result.zepto):
                    if listing is None:
                        continue
                    identity = '|'.join([response.location, str(response.demo_mode), listing.source, normalize_query(listing.title), normalize_query(listing.quantity_text or ''), listing.currency])
                    key = hashlib.sha256(identity.encode()).hexdigest()[:24]
                    listing.observation_id = key
                    if listing.available and math.isfinite(listing.price) and listing.price >= 0 and not response.cache.hit:
                        db.execute('INSERT OR IGNORE INTO observations VALUES (?, ?, ?)', (key, response.cache.fetched_at.isoformat(), listing.price))
                        db.execute('DELETE FROM observations WHERE key=? AND at NOT IN (SELECT at FROM observations WHERE key=? ORDER BY at DESC LIMIT 20)', (key, key))
                    rows = db.execute('SELECT at, price FROM observations WHERE key=? ORDER BY at DESC LIMIT 20', (key,)).fetchall()
                    listing.price_history = [PriceObservation(at=at, price=price) for at, price in reversed(rows)]
            # Cap total retained observations, including products no longer searched.
            db.execute('DELETE FROM observations WHERE rowid IN (SELECT rowid FROM observations ORDER BY at DESC LIMIT -1 OFFSET 10000)')
