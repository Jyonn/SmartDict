import unittest

import smartdict


GENERATED_KEY_CASES = [
    (
        "root-level generated key becomes visible next round",
        {
            "x": "y",
            "${x}": 123,
            "a": "${y}",
        },
        {
            "x": "y",
            "y": 123,
            "a": "${y}",
        },
        {
            "x": "y",
            "y": 123,
            "a": 123,
        },
    ),
    (
        "nested generated key becomes visible next round",
        {
            "env": "prod",
            "services": {
                "${env}": {
                    "url": "https://example.com",
                }
            },
            "selected": "${services.prod.url}",
        },
        {
            "env": "prod",
            "services": {
                "prod": {
                    "url": "https://example.com",
                }
            },
            "selected": "${services.prod.url}",
        },
        {
            "env": "prod",
            "services": {
                "prod": {
                    "url": "https://example.com",
                }
            },
            "selected": "https://example.com",
        },
    ),
    (
        "generated alias unlocks downstream lookup next round",
        {
            "key_name": "primary",
            "${key_name}": "model_a",
            "aliases": {
                "model_a": {
                    "target": "text-embedding-3-small",
                }
            },
            "resolved": "${aliases.${primary}.target}",
        },
        {
            "key_name": "primary",
            "primary": "model_a",
            "aliases": {
                "model_a": {
                    "target": "text-embedding-3-small",
                }
            },
            "resolved": "${aliases.${primary}.target}",
        },
        {
            "key_name": "primary",
            "primary": "model_a",
            "aliases": {
                "model_a": {
                    "target": "text-embedding-3-small",
                }
            },
            "resolved": "text-embedding-3-small",
        },
    ),
]


class TestIterativeGeneratedKeys(unittest.TestCase):
    def test_iteration_one_keeps_followup_reference_unresolved(self):
        for _, data, expected_first_pass, _ in GENERATED_KEY_CASES:
            with self.subTest(data=data):
                self.assertEqual(
                    smartdict.iterative_parse(data, iterations=1),
                    expected_first_pass,
                )

    def test_iteration_two_exposes_generated_keys_to_followup_references(self):
        for _, data, _, expected_second_pass in GENERATED_KEY_CASES:
            with self.subTest(data=data):
                self.assertEqual(
                    smartdict.iterative_parse(data, iterations=2),
                    expected_second_pass,
                )


if __name__ == "__main__":
    unittest.main()
