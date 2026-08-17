"""In-memory state for the Etsy simulator — reset between test runs via
`reset()`, and naturally reset on every server restart in local dev. Nothing
here is meant to survive a restart; this stands in for Etsy's own servers,
not for anything we need to persist ourselves (see models/etsy_account.py
and models/etsy_listing_sync.py for what we actually persist).
"""
import itertools
import time

DEFAULT_SHOP_ID = "12345678"
DEFAULT_SHOP_NAME = "Patti's Test Shop"

AUTH_CODE_TTL_SECONDS = 300
ACCESS_TOKEN_TTL_SECONDS = 3600

_listing_id_counter = itertools.count(10_000_000)
_receipt_id_counter = itertools.count(4_000_000_000)
_transaction_id_counter = itertools.count(5_000_000_000)


class Store:
    def __init__(self):
        self.reset()

    def reset(self):
        self.shops: dict[str, dict] = {DEFAULT_SHOP_ID: {"shop_id": DEFAULT_SHOP_ID, "shop_name": DEFAULT_SHOP_NAME}}
        self.auth_codes: dict[str, dict] = {}
        self.access_tokens: dict[str, dict] = {}
        self.refresh_tokens: dict[str, dict] = {}
        self.listings: dict[str, dict] = {}
        self.receipts: dict[str, dict] = {}
        # api_key -> list of request timestamps, for the QPS/QPD limiter
        self.request_log: dict[str, list[float]] = {}

    def next_listing_id(self) -> str:
        return str(next(_listing_id_counter))

    def next_receipt_id(self) -> str:
        return str(next(_receipt_id_counter))

    def next_transaction_id(self) -> str:
        return str(next(_transaction_id_counter))

    def prune_expired(self):
        now = time.time()
        self.auth_codes = {k: v for k, v in self.auth_codes.items() if v["expires_at"] > now}
        self.access_tokens = {k: v for k, v in self.access_tokens.items() if v["expires_at"] > now}


store = Store()
