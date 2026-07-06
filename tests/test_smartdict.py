import unittest

import smartdict
from smartdict.smartdict import CircularReferenceError, ReferenceNotFoundError


class SmartDictReferenceResolutionTests(unittest.TestCase):
    def test_dict_subclass_is_resolved_recursively(self):
        class ConfigDict(dict):
            pass

        parsed = smartdict.parse(ConfigDict({
            "name": "smartdict",
            "message": "hello-${name}",
            "nested": ConfigDict({
                "path": "/opt/${name}",
            }),
        }))

        self.assertEqual(parsed["message"], "hello-smartdict")
        self.assertEqual(parsed["nested"]["path"], "/opt/smartdict")

    def test_list_subclass_items_are_resolved_recursively(self):
        class ValueList(list):
            pass

        parsed = smartdict.parse({
            "items": ValueList(["a", "${name}"]),
            "name": "b",
        })

        self.assertEqual(parsed["items"], ["a", "b"])

    def test_string_subclass_is_treated_as_reference_string(self):
        class RefString(str):
            pass

        parsed = smartdict.parse({
            "name": "smartdict",
            "message": RefString("hello-${name}"),
        })

        self.assertEqual(parsed["message"], "hello-smartdict")

    def test_partial_reference_in_string_resolves_inline(self):
        data = {
            "name": "smartdict",
            "message": "hello-${name}",
        }

        parsed = smartdict.parse(data)

        self.assertEqual(parsed["message"], "hello-smartdict")

    def test_full_match_reference_returns_original_object(self):
        data = {
            "config": {"debug": True},
            "selected": "${config}$",
        }

        parsed = smartdict.parse(data)

        self.assertEqual(parsed["selected"], {"debug": True})

    def test_default_values_are_cast_to_expected_types(self):
        data = {
            "int_value": "${missing:42}$",
            "bool_value": "${missing:true}$",
            "null_value": "${missing:null}$",
            "text_value": "${missing:fallback}$",
        }

        parsed = smartdict.parse(data)

        self.assertEqual(parsed["int_value"], 42)
        self.assertIs(parsed["bool_value"], True)
        self.assertIsNone(parsed["null_value"])
        self.assertEqual(parsed["text_value"], "fallback")

    def test_list_and_tuple_indices_can_be_referenced(self):
        data = {
            "items": ["a", "b"],
            "pair": ("x", "y"),
            "pick_list": "${items.1}",
            "pick_tuple": "${pair.0}",
        }

        parsed = smartdict.parse(data)

        self.assertEqual(parsed["pick_list"], "b")
        self.assertEqual(parsed["pick_tuple"], "x")

    def test_dict_key_can_be_generated_from_reference(self):
        parsed = smartdict.parse({
            "name": "k",
            "${name}": 1,
        })

        self.assertEqual(parsed, {"name": "k", "k": 1})

    def test_nested_reference_string_resolves_indirect_key(self):
        data = {
            "env": "prod",
            "keys": {"prod": "url"},
            "url": "https://x",
            "result": "${${keys.${env}}}",
        }

        parsed = smartdict.parse(data)

        self.assertEqual(parsed["result"], "https://x")

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

    def test_iterative_parse_resolves_multi_hop_reference(self):
        parsed = smartdict.iterative_parse({
            "a": "${b}",
            "b": "${c}",
            "c": "ok",
        }, iterations=2)

        self.assertEqual(parsed, {"a": "ok", "b": "ok", "c": "ok"})

    def test_partial_parse_keeps_unresolved_placeholder_syntax(self):
        parsed = smartdict.partial_parse({
            "a": "${missing}",
            "b": "pre-${missing}-post",
            "c": "${missing}$",
        })

        self.assertEqual(parsed, {
            "a": "${missing}",
            "b": "pre-${missing}-post",
            "c": "${missing}$",
        })

    def test_missing_reference_raises_in_strict_mode(self):
        with self.assertRaises(ReferenceNotFoundError):
            smartdict.parse({
                "a": "${missing}",
            })

    def test_nested_missing_reference_in_dict_raises_in_strict_mode(self):
        with self.assertRaises(ReferenceNotFoundError):
            smartdict.parse({
                "app": {
                    "profile": "prod",
                },
                "services": {
                    "prod": {
                        "url": "${config.endpoints.api}",
                    },
                },
                "result": "${services.${app.profile}.url}",
            })

    def test_cross_nested_cycle_is_reported(self):
        with self.assertRaises(CircularReferenceError):
            smartdict.parse({
                "app": {
                    "profile": "${services.primary.profile}$",
                },
                "services": {
                    "primary": {
                        "profile": "${app.profile}$",
                    },
                },
            })

    def test_duplicate_key_after_nested_key_resolution_raises(self):
        with self.assertRaises(KeyError):
            smartdict.parse({
                "aliases": {
                    "primary": "stable",
                },
                "${aliases.primary}": 1,
                "stable": 2,
            })

    def test_real_cycle_is_still_reported(self):
        with self.assertRaises(CircularReferenceError):
            smartdict.parse({
                "a": "${b}$",
                "b": "${a}$",
            })


if __name__ == "__main__":
    unittest.main()
