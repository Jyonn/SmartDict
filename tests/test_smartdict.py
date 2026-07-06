import unittest

import smartdict
from smartdict.smartdict import CircularReferenceError


class SmartDictReferenceResolutionTests(unittest.TestCase):
    def test_nested_sibling_reference_does_not_trigger_false_cycle(self):
        data = {
            "a": {
                "x": "1",
                "y": "${a.x}/2",
            }
        }

        parsed = smartdict.parse(data)

        self.assertEqual(parsed["a"]["x"], "1")
        self.assertEqual(parsed["a"]["y"], "1/2")

    def test_intermediate_string_alias_still_resolves_to_target_container(self):
        data = {
            "alias": "${config}$",
            "config": {
                "name": "smartdict",
            },
            "result": "${alias.name}",
        }

        parsed = smartdict.parse(data)

        self.assertEqual(parsed["alias"], {"name": "smartdict"})
        self.assertEqual(parsed["result"], "smartdict")

    def test_real_cycle_is_still_reported(self):
        with self.assertRaises(CircularReferenceError):
            smartdict.parse({
                "a": "${b}$",
                "b": "${a}$",
            })


if __name__ == "__main__":
    unittest.main()
