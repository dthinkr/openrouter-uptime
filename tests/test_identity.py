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


if __name__ == "__main__":
    unittest.main()
