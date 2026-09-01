import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("poll", ROOT / "scripts" / "poll.py")
POLL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLL)


class EndpointIdentityTest(unittest.TestCase):
    def test_tags_distinguish_same_provider(self):
        a = {"model": "google/gemini", "provider": "Google",
             "endpoint_tag": "google/global", "endpoint_id": "google/global"}
        b = {"model": "google/gemini", "provider": "Google",
             "endpoint_tag": "google/priority", "endpoint_id": "google/priority"}
        self.assertNotEqual(POLL.endpoint_identity(a), POLL.endpoint_identity(b))
        POLL.validate_unique_endpoints([a, b])

    def test_duplicate_tag_stops_write(self):
        row = {"model": "m", "provider": "p", "endpoint_tag": "p/global",
               "endpoint_id": "p/global"}
        with self.assertRaises(RuntimeError):
            POLL.validate_unique_endpoints([row, dict(row)])

    def test_duplicate_tags_get_fingerprints(self):
        eps = [
            {"tag": "google/global", "provider_name": "Google",
             "pricing": {"prompt": "1"}, "supported_parameters": ["tools"]},
            {"tag": "google/global", "provider_name": "Google",
             "pricing": {"prompt": "2"}, "supported_parameters": []},
        ]
        ids = POLL.make_endpoint_ids(eps)
        identities = POLL.make_endpoint_identities(eps)
        self.assertEqual(len(ids), 2)
        self.assertNotEqual(ids[0], ids[1])
        self.assertTrue(all(x.startswith("google/global#") for x in ids))
        self.assertTrue(all(ambiguous for _, ambiguous in identities))

    def test_unique_tag_uses_stable_tag_and_duplicate_is_ambiguous(self):
        first = {"tag": "google/global", "provider_name": "Google",
                 "pricing": {"prompt": "1"}, "supported_parameters": ["tools"]}
        second = {"tag": "google/global", "provider_name": "Google",
                  "pricing": {"prompt": "2"}, "supported_parameters": []}
        alone = POLL.make_endpoint_identities([first])[0]
        together = POLL.make_endpoint_identities([first, second])
        self.assertEqual(alone, ("google/global", False))
        self.assertTrue(all(ambiguous for _, ambiguous in together))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# The shape Baseten published on 2026-09-01: two endpoints for one model that
# agree on every descriptive field the fingerprint reads and differ only in a
# measurement. There is nothing stable to tell them apart by.
BASETEN_A = {
    "tag": "baseten/fp4", "name": "Baseten | openai/gpt-oss-120b",
    "model_id": "openai/gpt-oss-120b", "provider_name": "Baseten",
    "pricing": {"prompt": "0.0000001", "completion": "0.0000005"},
    "quantization": "fp4", "context_length": 131072,
    "max_completion_tokens": None, "max_prompt_tokens": None,
    "supported_parameters": ["max_tokens", "tools"],
    "supports_implicit_caching": False,
    "status": 0, "uptime_last_5m": 100, "uptime_last_30m": 100,
    "uptime_last_1d": 100,
}
BASETEN_B = dict(BASETEN_A, uptime_last_1d=99.99197298165083)

GOOGLE_A = {"tag": "google/global", "provider_name": "Google",
            "pricing": {"prompt": "1"}, "supported_parameters": ["tools"]}
GOOGLE_B = {"tag": "google/global", "provider_name": "Google",
            "pricing": {"prompt": "2"}, "supported_parameters": []}
UNIQUE = {"tag": "novita/fp8", "provider_name": "Novita"}


class IndistinguishableDuplicateTest(unittest.TestCase):
    def test_indistinguishable_duplicates_are_kept_and_unique(self):
        # Both readings are real observations; refusing the snapshot over
        # them threw away 419 models' worth of readings every 15 minutes.
        identities = POLL.make_endpoint_identities([BASETEN_A, BASETEN_B])
        ids = [i for i, _ in identities]
        self.assertEqual(len(set(ids)), 2)
        self.assertTrue(all(i.startswith("baseten/fp4#") for i in ids))
        self.assertTrue(all(ambiguous for _, ambiguous in identities))
        rows = [{"model": "m", "endpoint_id": i} for i in ids]
        POLL.validate_unique_endpoints(rows)

    def test_ordinal_follows_array_order_and_is_deterministic(self):
        # audit.py replays raw/ and demands byte-identical derived rows, so
        # the tiebreak has to be a pure function of the archived list.
        first = POLL.make_endpoint_identities([BASETEN_A, BASETEN_B])
        again = POLL.make_endpoint_identities([BASETEN_A, BASETEN_B])
        self.assertEqual(first, again)
        self.assertTrue(first[0][0].endswith("#1"))
        self.assertTrue(first[1][0].endswith("#2"))
        fingerprint = first[0][0].rsplit("#", 1)[0]
        self.assertEqual(first[1][0].rsplit("#", 1)[0], fingerprint)

    def test_distinguishable_duplicates_keep_their_historical_ids(self):
        # Every fingerprinted ID already committed to derived/ must replay
        # unchanged, or the audit's exact-match check fails on old snapshots.
        ids = POLL.make_endpoint_ids([GOOGLE_A, GOOGLE_B])
        self.assertTrue(all(i.count("#") == 1 for i in ids), ids)
        self.assertEqual(POLL.make_endpoint_ids([UNIQUE]), ["novita/fp8"])

    def test_all_three_identity_copies_agree(self):
        # poll.py writes, rebuild_history.py re-derives for the audit, and
        # reparse.py re-derives by hand. They are copies on purpose; this is
        # what catches a fix applied to one of them.
        rebuild, reparse = _load("rebuild_history"), _load("reparse")
        for eps in ([BASETEN_A, BASETEN_B], [GOOGLE_A, GOOGLE_B],
                    [UNIQUE, BASETEN_A, BASETEN_B, GOOGLE_A]):
            expected = POLL.make_endpoint_identities(eps)
            self.assertEqual(rebuild.endpoint_identities(eps), expected)
            self.assertEqual(reparse.endpoint_identities(eps), expected)


if __name__ == "__main__":
    unittest.main()
