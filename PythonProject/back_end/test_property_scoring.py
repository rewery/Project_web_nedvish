import unittest
from property_scoring import area_score, filter_by_budget, estimate_market_price, score_listing_features, price_score_from_market_deviation
import json
from pathlib import Path

class PropertyScoringTests(unittest.TestCase):
    def test_area_soft_decline(self):
        self.assertEqual(area_score(45, 45), 100)
        self.assertEqual(area_score(40, 45), 100)
        self.assertEqual(area_score(51, 45), 95)
        self.assertEqual(area_score(52, 45), 90)
        self.assertEqual(area_score(55, 45), 75)
        self.assertEqual(area_score(60, 45), 50)

    def test_minimum_only_budget(self):
        rows = [{"price": 4}, {"price": 6}, {"price": 9}]
        selected, rejected = filter_by_budget(rows, {"mode": "min_price", "min_price": 6})
        self.assertEqual([row["price"] for row in selected], [6, 9])
        self.assertEqual(rejected, 1)

    def test_budget_modes_are_exclusive(self):
        rows = [{'price': 5}, {'price': 7}, {'price': 9}]
        selected, rejected = filter_by_budget(rows, {'mode': 'max_price', 'max_price': 8})
        self.assertEqual([x['price'] for x in selected], [5, 7])
        self.assertEqual(rejected, 1)
        selected, rejected = filter_by_budget(rows, {'mode': 'price_range', 'min_price': 6, 'max_price': 8})
        self.assertEqual([x['price'] for x in selected], [7])
        self.assertEqual(rejected, 2)

    def test_market_requires_same_district(self):
        target = {'id': 'a', 'district': 'Центр', 'area': 50, 'rooms': 2, 'price': 5_000_000}
        rows = [target] + [
            {'id': str(i), 'district': 'Центр', 'area': 49 + i % 3, 'rooms': 2, 'price': 4_900_000}
            for i in range(3)
        ]
        self.assertEqual(estimate_market_price(target, rows)['status'], 'estimated')
        target.pop('district')
        self.assertEqual(estimate_market_price(target, rows)['status'], 'insufficient_data')


    def test_market_relative_price_score(self):
        self.assertEqual(price_score_from_market_deviation(-40), 100)
        self.assertEqual(price_score_from_market_deviation(-20), 75)
        self.assertEqual(price_score_from_market_deviation(0), 50)
        self.assertEqual(price_score_from_market_deviation(20), 25)
        self.assertEqual(price_score_from_market_deviation(40), 0)
        self.assertIsNone(price_score_from_market_deviation(None))

    def test_market_analysis_contains_price_score(self):
        target = {'id': 'a', 'district': 'Центр', 'area': 50, 'rooms': 2, 'price': 4_000_000}
        rows = [target] + [
            {'id': str(i), 'district': 'Центр', 'area': 50, 'rooms': 2, 'price': 5_000_000}
            for i in range(3)
        ]
        result = estimate_market_price(target, rows)
        self.assertEqual(result['status'], 'estimated')
        self.assertEqual(result['deviation_percent'], -20.0)
        self.assertEqual(result['price_score'], 75.0)

    def test_imports_all_50_sample_apartments(self):
        source = Path(__file__).with_name('demo_apartments_yoshkar_ola.json')
        if not source.exists():
            self.skipTest('Исходный пользовательский TXT не включён в репозиторий')
        rows = json.loads(source.read_text(encoding='utf-8'))['listings']
        self.assertEqual(len(rows), 50)
        self.assertEqual(rows[0]['price'], 3_000_000)
        self.assertEqual(rows[-1]['id'], 'yola-50')

    def test_missing_metro_is_not_fabricated(self):
        profile = {'target_area': 45}
        scores = score_listing_features({'area': 46, 'metro_minutes': None}, profile)
        self.assertIn('area', scores)
        self.assertNotIn('metro', scores)

if __name__ == '__main__':
    unittest.main()
