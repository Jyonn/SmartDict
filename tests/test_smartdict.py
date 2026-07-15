import unittest
from contextlib import redirect_stdout
from io import StringIO

import smartdict
from smartdict.smartdict import CircularReferenceError, ReferenceNotFoundError


class SmartDictReferenceResolutionTests(unittest.TestCase):
    def test_object_attribute_can_be_referenced(self):
        class A:
            def __init__(self):
                self.x = "value"

        parsed = smartdict.parse({
            "a": A(),
            "b": "${a.x}",
        })

        self.assertEqual(parsed["b"], "value")

    def test_nested_object_attribute_can_be_referenced(self):
        class Child:
            def __init__(self):
                self.name = "smartdict"

        class Parent:
            def __init__(self):
                self.child = Child()

        parsed = smartdict.parse({
            "a": Parent(),
            "b": "hello-${a.child.name}",
        })

        self.assertEqual(parsed["b"], "hello-smartdict")

    def test_object_attribute_and_dict_path_can_be_mixed(self):
        class Config:
            def __init__(self):
                self.profile = "prod"

        parsed = smartdict.parse({
            "app": Config(),
            "services": {
                "prod": {
                    "url": "https://example.com",
                },
            },
            "result": "${services.${app.profile}.url}",
        })

        self.assertEqual(parsed["result"], "https://example.com")

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

    def test_single_reference_preserves_native_value_type(self):
        parsed = smartdict.parse({
            "config": {"debug": True},
            "selected": "${config}",
        })

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

    def test_json_list_default_preserves_native_type(self):
        parsed = smartdict.parse({
            "sinkhorn_epsilon": "${sid_sinkhorn_epsilon:[0.0, 0.0, 0.003]}",
        })

        self.assertEqual(parsed["sinkhorn_epsilon"], [0.0, 0.0, 0.003])
        self.assertIsInstance(parsed["sinkhorn_epsilon"], list)

    def test_json_dict_default_preserves_native_type(self):
        parsed = smartdict.parse({
            "value": '${config:{"hello": "world"}}',
        })

        self.assertEqual(parsed["value"], {"hello": "world"})
        self.assertIsInstance(parsed["value"], dict)

    def test_json_dict_default_allows_colons_inside_values(self):
        parsed = smartdict.parse({
            "value": '${config:{"hello": "a:b", "url": "https://example.com"}}',
        })

        self.assertEqual(parsed["value"], {
            "hello": "a:b",
            "url": "https://example.com",
        })

    def test_existing_reference_still_wins_over_json_default(self):
        parsed = smartdict.parse({
            "sid_sinkhorn_epsilon": [1.0, 2.0, 3.0],
            "sinkhorn_epsilon": "${sid_sinkhorn_epsilon:[0.0, 0.0, 0.003]}",
        })

        self.assertEqual(parsed["sinkhorn_epsilon"], [1.0, 2.0, 3.0])

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

    def test_iterative_parse_exposes_generated_dict_key_on_next_round(self):
        data = {
            "x": "y",
            "${x}": 123,
            "a": "${y}",
        }

        first_pass = smartdict.iterative_parse(data, iterations=1)
        second_pass = smartdict.iterative_parse(data, iterations=2)

        self.assertEqual(first_pass, {
            "x": "y",
            "y": 123,
            "a": "${y}",
        })
        self.assertEqual(second_pass, {
            "x": "y",
            "y": 123,
            "a": 123,
        })

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

    def test_nested_default_expression_can_fall_back_to_other_reference(self):
        parsed = smartdict.parse({
            "repr_source_model": "text-embedding-3-small",
            "embedding_model": "${sid_embedding_model:${repr_source_model:null}}",
        })

        self.assertEqual(parsed["embedding_model"], "text-embedding-3-small")

    def test_nested_default_expression_can_resolve_to_none(self):
        parsed = smartdict.parse({
            "embedding_model": "${sid_embedding_model:${repr_source_model:null}}",
        })

        self.assertIsNone(parsed["embedding_model"])

    def test_nested_default_expression_prefers_primary_reference(self):
        parsed = smartdict.parse({
            "sid_embedding_model": "bge-m3",
            "repr_source_model": "text-embedding-3-small",
            "embedding_model": "${sid_embedding_model:${repr_source_model:null}}",
        })

        self.assertEqual(parsed["embedding_model"], "bge-m3")

    def test_nested_default_expression_preserves_scalar_type(self):
        parsed = smartdict.parse({
            "value": "${primary:${fallback:42}}",
        })

        self.assertEqual(parsed["value"], 42)
        self.assertIsInstance(parsed["value"], int)

    def test_missing_reference_raises_in_strict_mode(self):
        with self.assertRaises(ReferenceNotFoundError):
            smartdict.parse({
                "a": "${missing}",
            })

    def test_missing_reference_error_contains_details_without_stdout_output(self):
        stdout = StringIO()
        with redirect_stdout(stdout):
            with self.assertRaises(ReferenceNotFoundError) as ctx:
                smartdict.parse({
                    "a": "${missing}",
                })

        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(len(ctx.exception.unresolved), 1)
        self.assertEqual(ctx.exception.unresolved[0].path, "a")
        self.assertEqual(ctx.exception.unresolved[0].reference, "missing")
        self.assertIn("a -> missing", str(ctx.exception))

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

    def test_nested_missing_reference_error_contains_leaf_path(self):
        with self.assertRaises(ReferenceNotFoundError) as ctx:
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

        self.assertEqual(len(ctx.exception.unresolved), 1)
        self.assertEqual(ctx.exception.unresolved[0].path, "services → prod → url")
        self.assertEqual(ctx.exception.unresolved[0].reference, "config.endpoints.api")

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

    def test_iterations_must_be_greater_than_zero(self):
        with self.assertRaises(ValueError):
            smartdict.iterative_parse({
                "a": "${b}",
                "b": "ok",
            }, iterations=0)


if __name__ == "__main__":
    unittest.main()
