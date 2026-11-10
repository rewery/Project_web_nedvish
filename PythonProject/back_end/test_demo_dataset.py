import unittest
from demo_dataset import parse_apartment_text_content

class DemoDatasetImportTests(unittest.TestCase):
    def test_parses_multiple_user_text_listings(self):
        text = "Квартира №1\nКоличество комнат: 2\nЦена квартиры: 5 000 000 руб\nПлощадь: 50 м²\nРайон: Центр\n\nКвартира №2\nЦена: 6 000 000 ₽\nОбщая площадь: 60 м²"
        rows, errors = parse_apartment_text_content(text, "Казань")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["city"], "Казань")
        self.assertEqual(rows[0]["district"], "Центр")
        self.assertEqual(rows[1]["price"], 6000000)
        self.assertEqual(errors, [])

    def test_reports_unreadable_blocks(self):
        rows, errors = parse_apartment_text_content("Квартира №1\nЦена: 5 000 000 руб")
        self.assertEqual(rows, [])
        self.assertTrue(errors)

if __name__ == "__main__":
    unittest.main()
