"""Pure parser/snapshot tests; no Camoufox binary or browser download is required."""

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from urllib.parse import urlsplit


def load_worker():
    # worker.py imports Camoufox at module load. The cases here cover only pure
    # protocol helpers, so inject a minimal module rather than requiring it.
    camoufox = types.ModuleType("camoufox")
    camoufox.Camoufox = object
    camoufox.DefaultAddons = types.SimpleNamespace(UBO="ubo")
    camoufox.NewContext = object
    sys.modules["camoufox"] = camoufox
    path = Path(__file__).parents[2] / "main" / "resources" / "camoufox" / "worker.py"
    spec = importlib.util.spec_from_file_location("reader_camoufox_worker_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


worker = load_worker()


class WorkerCookieProtocolTest(unittest.TestCase):
    def test_domain_delete_fallback_is_forwarded_but_domain_creation_stays_browser_only(self):
        deleted = worker.parse_set_cookie(
            "sid=gone; Domain=example.test; Path=/; Max-Age=0",
            "https://books.example.test/logout",
        )
        self.assertFalse(deleted["hostOnly"])
        self.assertTrue(deleted["deleted"])

        # The caller accepts only host-only creations from raw headers. This is
        # what prevents the fallback from implementing public-suffix acceptance.
        self.assertFalse(deleted["hostOnly"] or deleted["deleted"] is False)

    def test_snapshot_leading_dot_remains_domain_scoped_without_header_metadata(self):
        cookie = worker.portable_snapshot_cookie(
            {"name": "wide", "value": "ok", "domain": ".example.test", "path": "/"},
            urlsplit("https://books.example.test/page"),
            {},
            {},
        )
        self.assertEqual("example.test", cookie["domain"])
        self.assertFalse(cookie["hostOnly"])

    def test_http_secure_fallback_is_rejected(self):
        self.assertIsNone(worker.parse_set_cookie(
            "sid=should-not-persist; Secure; Path=/",
            "http://books.example.test/login",
        ))

    def test_unchanged_imported_cookie_is_transient_but_response_change_is_returned(self):
        imported = {
            "name": "once", "value": "header", "domain": "books.example.test",
            "path": "/", "hostOnly": True, "secure": False, "httpOnly": False,
            "sameSite": None, "expires": -1, "deleted": False,
        }
        key = worker.cookie_identity(imported)
        self.assertFalse(worker.cookie_changed_from_initial(imported, {key: imported}, set()))

        refreshed = dict(imported, value="server")
        self.assertTrue(worker.cookie_changed_from_initial(refreshed, {key: imported}, {key}))

    def test_response_domain_deletion_remains_a_tombstone(self):
        deleted = worker.parse_set_cookie(
            "sid=; Domain=example.test; Path=/; Max-Age=0",
            "https://books.example.test/logout",
        )
        key = worker.cookie_identity(deleted)
        self.assertTrue(deleted["deleted"])
        self.assertTrue(worker.cookie_changed_from_initial(deleted, {}, {key}))


if __name__ == "__main__":
    unittest.main()
