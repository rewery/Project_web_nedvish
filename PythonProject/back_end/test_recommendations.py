import json
import unittest
from pathlib import Path

from recommendations import rank_properties


class RecommendationRankingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sample = json.loads((Path(__file__).with_name("recommendation_samples.json")).read_text(encoding="utf-8"))
        cls.profile = sample["profile"]
        cls.properties = sample["properties"]

    def test_returns_sorted_ratings(self):
        result = rank_properties(self.profile, self.properties)
        ratings = [row["rating"] for row in result if row["rating"] is not None]
        self.assertEqual(ratings, sorted(ratings, reverse=True))
        self.assertEqual(len(result), 3)

    def test_not_important_and_unspecified_are_not_used(self):
        result = rank_properties(self.profile, self.properties)
        first = result[0]
        used = {row["criterion"] for row in first["criterion_details"]}
        self.assertNotIn("building_condition", used)
        self.assertNotIn("price", used)
        self.assertNotIn("area", used)

    def test_missing_scores_are_not_zero(self):
        result = rank_properties(self.profile, [{"id": "empty", "criterion_scores": {}}])
        self.assertIsNone(result[0]["rating"])


if __name__ == "__main__":
    unittest.main()
