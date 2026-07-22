# Completed-Sales Import Format

MarktWert accepts UTF-8 CSV and modern `.xlsx` files. Imports are attached to
one existing tracked product and use its title inclusion/exclusion policy.
Preview validates and classifies rows without writing to the database.

## Required columns

Headers are case-insensitive and spaces are normalized.

| Canonical field | Accepted examples |
| --- | --- |
| Item ID | `item_id`, `ebay_item_id`, `Artikelnummer` |
| Title | `title`, `Titel`, `Artikelbezeichnung` |
| Sold price | `sold_price`, `price`, `Verkaufspreis`, `Preis` |
| Sold date | `sold_at`, `sold_date`, `Verkauft am`, `Verkaufsdatum` |

## Optional columns

`shipping_price`, `currency`, `condition`, `listing_format`, `best_offer`,
`bid_count`, `listing_url`, `thumbnail_url`, `location`, `seller_name`,
`seller_feedback_percentage`, `seller_feedback_count`, `brand`, `model`,
`part_number`, and `category` are supported. Common German equivalents are
recognized.

Currency defaults to EUR. German and international money forms such as
`299,99 €`, `299.99`, `1.299,99`, and `1,299.99` are accepted. Offset-free dates
are interpreted as Europe/Berlin by default and stored as UTC.

## Processing guarantees

- CSV is streamed; XLSX uses read-only workbook mode.
- Source files and expanded XLSX archives have bounded safety limits.
- Required schemas are checked before persistence.
- Invalid rows are quarantined in a bounded issue report.
- Valid rows are classified as accepted, excluded, or requiring review.
- Writes commit in configurable pages, enabling safe progress and cancellation.
- Source plus item ID prevents duplicate observations.
- Re-import can fill missing facts but does not overwrite known facts.
- Distinct source hashes are retained as revision history.
- Excluded/review rows remain auditable but are marked separately from accepted
  observations.
