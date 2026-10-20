import json
import unittest

from shivaay_memory.model_extraction import StructuredModelExtractor


class StructuredModelExtractorTests(unittest.TestCase):
    def test_parses_and_validates_model_candidates(self):
        def generate(prompt):
            self.assertIn('"role": "user"', prompt)
            return json.dumps([
                {"text": "User prefers concise answers.", "category": "preference",
                 "confidence": 0.9, "importance": 4, "reason": "Repeated preference"},
                {"text": "bad", "category": "goal", "confidence": 0.9, "importance": 4},
                {"text": "User prefers concise answers.", "category": "preference",
                 "confidence": 0.9, "importance": 4},
                {"text": "Unsupported idea goes here", "category": "made_up",
                 "confidence": 9, "importance": 99},
            ])
        candidates = StructuredModelExtractor(generate).extract([
            {"role": "user", "content": "Please keep answers concise."},
            {"role": "assistant", "content": "I think you prefer long essays."},
        ], project="SHIVAAY")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].project, "SHIVAAY")
        self.assertEqual(candidates[0].category, "preference")

    def test_rejects_non_json_output(self):
        extractor = StructuredModelExtractor(lambda prompt: "I think you like this.")
        with self.assertRaises(ValueError):
            extractor.extract([{"role": "user", "content": "Remember this preference."}])

    def test_empty_result_is_allowed(self):
        extractor = StructuredModelExtractor(lambda prompt: "[]")
        self.assertEqual(extractor.extract([{"role": "user", "content": "What is 2+2?"}]), [])

    def test_prompt_only_contains_user_messages(self):
        prompts = []
        extractor = StructuredModelExtractor(lambda prompt: prompts.append(prompt) or "[]")
        extractor.extract([
            {"role": "system", "content": "hidden system text"},
            {"role": "assistant", "content": "assistant text"},
            {"role": "user", "content": "User content"},
        ])
        self.assertIn("User content", prompts[0])
        self.assertNotIn("hidden system text", prompts[0])
        self.assertNotIn("assistant text", prompts[0])


if __name__ == "__main__":
    unittest.main()
