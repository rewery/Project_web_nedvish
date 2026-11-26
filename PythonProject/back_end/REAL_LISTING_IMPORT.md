# Real listing URL import (experimental)

This feature adds a conservative **user-provided URL importer**. It is not a crawler.
It fetches one listing URL at a time (or a batch of at most 10 explicitly provided URLs),
checks the source site's `robots.txt`, uses a descriptive User-Agent, does not log in,
does not bypass CAPTCHA/anti-bot systems, does not use proxies/stealth, and refuses
private/local IP targets and redirects. Only use sources that permit automated access
or for which you have permission.

## Endpoints

### Parse one listing
`POST /api/recommendations/import-url`

```json
{
  "url": "https://example.com/listing/123",
  "city": "Казань"
}
```

Returns `raw_listing`, normalized `listing`, `quality`, and extraction notes.

### Parse up to 10 URLs
`POST /api/recommendations/import-urls`

```json
{
  "city": "Казань",
  "urls": ["https://example.com/listing/123", "https://example.com/listing/456"]
}
```

### Import and rank immediately
`POST /api/recommendations/evaluate-urls`

```json
{
  "city": "Казань",
  "urls": ["https://example.com/listing/123"],
  "profile": {
    "target_area": 45,
    "priorities": {
      "price": {"level": "high"},
      "area": {"level": "medium"},
      "metro": {"level": "low"},
      "kindergarten": {"level": "not_important"},
      "school": {"level": "not_important"},
      "city_center": {"level": "medium"}
    }
  },
  "budget": {"mode": "max_price", "max_price": 8000000}
}
```

The third endpoint calls the existing budget filtering and ranking functions and includes
source links, photos (when extractable), and data-quality flags. Errors for individual
URLs are returned without aborting the batch.

## Extraction order

1. JSON-LD (schema.org structured data)
2. OpenGraph/Twitter metadata
3. Conservative labeled text fallback for price, area, rooms and floor

Missing or ambiguous values remain `null`. A successful HTTP response does **not**
mean that every field was extracted accurately. Compare values with the source listing.

## Supported dependencies

Install from `back_end`:

```bash
pip install -r requirements.txt
```

Run parser unit tests:

```bash
python -m unittest test_real_listing_import.py -v
```

Existing backend tests:

```bash
python -m unittest discover -s . -p 'test_*.py' -v
```

The importer is deliberately generic; many real estate sites render listing data in
client-side JavaScript or block automated access. Such pages may return sparse results.
Do not attempt to evade site controls. For stable production ingestion, prefer an
approved API, partner feed, licensed provider, or explicit written permission.
