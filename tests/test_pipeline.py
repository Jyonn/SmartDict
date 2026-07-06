import unittest

import smartdict
from smartdict.smartdict import PipelineStageError


class SmartDictPipelineTests(unittest.TestCase):
    def test_pipeline_applies_string_stages_left_to_right(self):
        parsed = smartdict.parse({
            "dataset": "  My Dataset  ",
            "save_dir": "${dataset|strip|lower|slug}",
        })

        self.assertEqual(parsed["save_dir"], "my-dataset")

    def test_pipeline_runs_after_default_value(self):
        parsed = smartdict.parse({
            "port": "${env.PORT:8000|int}",
        })

        self.assertEqual(parsed["port"], 8000)
        self.assertIsInstance(parsed["port"], int)

    def test_pipeline_runs_after_existing_value(self):
        parsed = smartdict.parse({
            "env": {
                "PORT": "9000",
            },
            "port": "${env.PORT:8000|int}",
        })

        self.assertEqual(parsed["port"], 9000)
        self.assertIsInstance(parsed["port"], int)

    def test_pipeline_can_parse_json_strings(self):
        parsed = smartdict.parse({
            "raw": '{"hello": "world"}',
            "value": "${raw|json}",
        })

        self.assertEqual(parsed["value"], {"hello": "world"})

    def test_pipeline_can_transform_json_default_values(self):
        parsed = smartdict.parse({
            "name": '${dataset:"My Dataset"|slug}',
        })

        self.assertEqual(parsed["name"], "my-dataset")

    def test_pipeline_can_consume_nested_default_expression(self):
        parsed = smartdict.parse({
            "repr_source_model": "TEXT-EMBEDDING-3-SMALL",
            "embedding_model": "${sid_embedding_model:${repr_source_model:null}|lower}",
        })

        self.assertEqual(parsed["embedding_model"], "text-embedding-3-small")

    def test_partial_parse_preserves_unresolved_pipeline_expression(self):
        parsed = smartdict.partial_parse({
            "save_dir": "${dataset|slug}",
        })

        self.assertEqual(parsed["save_dir"], "${dataset|slug}")

    def test_unknown_pipeline_stage_raises_structured_error(self):
        with self.assertRaises(PipelineStageError) as ctx:
            smartdict.parse({
                "value": "${name|wat}",
                "name": "smartdict",
            })

        self.assertEqual(ctx.exception.stage, "wat")

    def test_pipeline_stage_conversion_error_is_reported(self):
        with self.assertRaises(PipelineStageError) as ctx:
            smartdict.parse({
                "port": "${env.PORT:abc|int}",
            })

        self.assertEqual(ctx.exception.stage, "int")
        self.assertIn("Pipeline stage `int` failed", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
