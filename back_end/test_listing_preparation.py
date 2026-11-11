import json
import unittest
from pathlib import Path
from listing_preparation import prepare_listing, prepare_search_listings

class ListingPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = json.loads(Path(__file__).with_name('listing_samples_yoshkar_ola.json').read_text(encoding='utf-8'))
        cls.city, cls.listings = data['city'], data['listings']

    def test_prepares_all_same_city_listings(self):
        result = prepare_search_listings(self.listings, self.city)
        self.assertEqual(len(result), 6)
        self.assertTrue(all(item['city'] == self.city for item in result))

    def test_calculates_price_per_sqm_if_missing(self):
        item = prepare_listing({'price': 4000000, 'area': 32.0})
        self.assertEqual(item['price_per_sqm'], 125000)

    def test_unknown_condition_stays_unknown(self):
        item = prepare_listing({'description': 'Продаётся квартира в хорошем районе'})
        self.assertIsNone(item['features']['apartment_condition']['value'])

    def test_rejects_other_city(self):
        rows = self.listings + [{'id':'other','city':'Казань','price':1,'area':1}]
        self.assertEqual(len(prepare_search_listings(rows, self.city)), 6)

if __name__ == '__main__':
    unittest.main()
