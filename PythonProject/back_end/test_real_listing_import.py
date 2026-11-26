import unittest
from real_listing_import import extract_listing_from_html


class RealListingImportParserTests(unittest.TestCase):
    def test_jsonld_offer_apartment(self):
        html = """
        <html><head><title>Квартира</title>
        <script type="application/ld+json">
        {"@context":"https://schema.org","@type":"Apartment",
         "name":"2-комнатная квартира","description":"После ремонта",
         "floorSize":{"@type":"QuantitativeValue","value":48.5,"unitCode":"MTK"},
         "numberOfRooms":2,"floorLevel":5,"numberOfFloors":16,
         "address":{"@type":"PostalAddress","streetAddress":"ул. Ленина, 10","addressLocality":"Казань"},
         "offers":{"@type":"Offer","price":"7200000","priceCurrency":"RUB"},
         "image":"https://example.org/photo.jpg"}
        </script></head><body></body></html>
        """
        item = extract_listing_from_html(html, "https://example.org/offer/1", "Казань")
        self.assertEqual(item["price"], 7200000)
        self.assertEqual(item["area"], 48.5)
        self.assertEqual(item["rooms"], 2)
        self.assertEqual(item["floor"], 5)
        self.assertEqual(item["total_floors"], 16)
        self.assertEqual(item["city"], "Казань")
        self.assertEqual(item["source_url"], "https://example.org/offer/1")

    def test_fallback_extracts_explicit_text(self):
        html = "<html><body>Цена: 5 500 000 руб. Площадь: 37,2 м² 2-комнатная 4/9 этаж</body></html>"
        item = extract_listing_from_html(html, "https://example.org/a", "Тест")
        self.assertEqual(item["price"], 5500000)
        self.assertEqual(item["area"], 37.2)
        self.assertEqual(item["rooms"], 2)
        self.assertEqual(item["floor"], 4)
        self.assertEqual(item["total_floors"], 9)

    def test_missing_values_are_none(self):
        item = extract_listing_from_html("<html><title>Объект</title></html>", "https://example.org/x")
        self.assertIsNone(item["price"])
        self.assertIsNone(item["area"])
        self.assertIsNone(item["rooms"])


if __name__ == "__main__":
    unittest.main()
