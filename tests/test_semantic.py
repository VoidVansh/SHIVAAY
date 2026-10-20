import tempfile
import unittest
from pathlib import Path

from shivaay_memory.engine import MemoryEngine
from shivaay_memory.semantic import SemanticMemoryIndex, cosine_similarity, OllamaEmbeddingBackend


class FakeEmbeddings:
    model = "test-embeddings"
    def __init__(self):
        self.calls = []
    vectors = {
        "My computer should work offline": [1.0, 0.0],
        "I want the app to work without internet": [0.95, 0.05],
        "Chocolate cake recipe": [0.0, 1.0],
    }
    def embed(self, text):
        self.calls.append(text)
        return self.vectors.get(text, [0.9, 0.1])


class SemanticTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.engine = MemoryEngine(str(Path(self.tempdir.name) / "test.sqlite3"))
        self.backend = FakeEmbeddings()
        self.index = SemanticMemoryIndex(self.engine, self.backend)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_cosine_similarity(self):
        self.assertAlmostEqual(cosine_similarity([1, 0], [1, 0]), 1.0)
        self.assertEqual(cosine_similarity([1, 0], [0, 1]), 0.0)
        self.assertEqual(cosine_similarity([1], [1, 0]), 0.0)

    def test_semantic_search_finds_different_wording(self):
        first = self.engine.add_memory("My computer should work offline", project="SHIVAAY")
        self.engine.add_memory("Chocolate cake recipe", project="cooking")
        self.index.index_memory(first)
        results = self.index.search("I want the app to work without internet", project="SHIVAAY")
        self.assertEqual([row["id"] for row in results], [first])
        self.assertGreater(results[0]["semantic_score"], 0.9)

    def test_index_all_reuses_current_model_vectors_and_can_rebuild(self):
        self.engine.add_memory("My computer should work offline", project="SHIVAAY")
        self.assertEqual(self.index.index_all(project="SHIVAAY"), 1)
        self.assertEqual(self.index.index_all(project="SHIVAAY"), 0)
        self.assertEqual(self.index.index_all(project="SHIVAAY", force=True), 1)
        self.assertEqual(len(self.backend.calls), 2)

    def test_hybrid_search_fuses_lexical_and_semantic_results(self):
        first = self.engine.add_memory("My computer should work offline", project="SHIVAAY", importance=5)
        self.engine.add_memory("Chocolate cake recipe", project="cooking")
        self.index.index_memory(first)
        results = self.index.hybrid_search("I want the app to work without internet", project="SHIVAAY")
        self.assertEqual(results[0]["id"], first)
        self.assertIn("semantic", results[0]["retrieval_sources"])
        self.assertIn("lexical", results[0]["retrieval_sources"])
        self.assertGreater(results[0]["hybrid_score"], 0)

    def test_remote_embedding_host_rejected(self):
        with self.assertRaises(ValueError):
            OllamaEmbeddingBackend(host="http://127.0.0.1.attacker.invalid:11434")

    def test_indexing_missing_memory_fails(self):
        with self.assertRaises(KeyError):
            self.index.index_memory(999)


if __name__ == "__main__":
    unittest.main()
