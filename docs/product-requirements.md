# Product Requirements

## 1. Product objective

MarktWert helps professional computer-hardware resellers evaluate the German
secondary market. It converts historical completed-sale records into traceable
market statistics, acquisition limits, trend signals, and deal candidates.

The desktop-first product targets Windows, remains usable offline for previously
stored data, and keeps user data local by default.

## 2. Users and primary workflows

### Professional reseller

1. Search for a hardware product or select a saved search.
2. Refine condition, format, brand, price, and date filters.
3. Review accepted and excluded observations with exclusion reasons.
4. Inspect robust price statistics, history, demand, and liquidity.
5. Enter a target profit and costs to calculate a maximum purchase price.
6. Save the search, export evidence, or create a watch rule.

### Data operator

1. Configure an authorized source and update policy.
2. Monitor imports, retries, rejected records, and freshness.
3. Back up, restore, and validate the local database.

## 3. Functional requirements

### Acquisition and provenance

- Support multiple data sources through adapters: approved eBay APIs or feeds,
  user CSV/Excel imports, and an explicitly authorized browser adapter.
- Capture listing identity, title, money values, sale date, seller facts,
  condition, format, bids, catalog attributes, URL, image reference, currency,
  location, source, acquisition time, and raw-record checksum.
- Use source plus external item ID as the canonical uniqueness boundary.
- Store an immutable observation history and enrich only absent or newer fields.
- Persist sync cursors and retry state so interrupted updates can resume.
- Record provenance and parser version for every imported observation.

### Search and filtering

- Provide fast local full-text search and recent/favorite searches.
- Filter Germany, condition, listing format, shipping treatment, brand, price,
  sale date, and product attributes.
- Apply configurable exclusion rules for defective items, accessories, empty
  packaging, and replacement parts.
- Explain every automatic exclusion and allow non-destructive user overrides.

### Title normalization

- Extract deterministic hardware attributes before invoking an AI provider.
- Normalize equivalent product titles while preserving the original title.
- Version normalization models/rules and retain confidence and evidence.
- Require low-confidence results to remain `unknown`, never silently guessed.
- Make external AI optional and redact personal or unnecessary listing data.

### Analytics

- Calculate count, mean, median, minimum, maximum, standard deviation, average
  shipping, daily/weekly/monthly sales, trends, and volatility.
- Support 7, 30, 90, 180, and 365-day and all-time windows.
- Render price history, moving average, histogram, box plot, sales frequency,
  grouped comparisons, and weekly/monthly trends.
- Distinguish asking prices from observed sold prices throughout the UI.
- Surface sample size, time window, currency, exclusions, and data freshness
  alongside every derived result.

### Purchase recommendation

- Accept desired profit, marketplace fee assumptions, outbound shipping,
  refurbishment/contingency costs, and taxes where applicable.
- Return maximum acquisition cost, expected sale price and costs, expected
  profit, and ROI.
- Store the complete assumption set with each saved recommendation.

### Market and deal analysis

- Derive demand, supply, saturation, interval-between-sales, liquidity, and trend
  with documented formulas and confidence.
- Compare current authorized listings with comparable historical observations.
- Rank candidates using user discount thresholds and net-margin estimates.

### Watchlists, alerts, and organization

- Save unlimited local watch definitions and favorite searches.
- Group favorites into GPU, CPU, motherboard, RAM, SSD, PSU, monitor, printer,
  and user-defined categories.
- Schedule authorized updates and create in-app price, trend, and demand alerts.

### Data interchange

- Export CSV, JSON, Excel, PDF reports, and PNG charts.
- Import validated CSV and Excel data with a preview and error report.
- Create and restore transactional database backups.

### Settings and operations

- Configure theme, locale, paths, acquisition limits, worker count, cache,
  update interval, assumptions, and retention.
- Separate application, acquisition, database, and performance logs.
- Display last successful update and meaningful background-job status.

## 4. Non-functional requirements

- Python 3.12+ and a supported PySide6 release.
- Responsive UI: network, database migrations, imports, and analytics never run
  on the Qt UI thread.
- Local search feedback should normally appear within 150 ms for cached queries;
  long operations must expose progress and cancellation.
- SQLite uses WAL mode, foreign keys, bounded transactions, migrations, and
  verified backups. A single process owns writes.
- Decimal integer minor units represent money; floating point is not used for
  persisted monetary values.
- All timestamps are timezone-aware UTC internally and localized for display.
- Inputs, imported schemas, paths, URLs, and external payloads are validated.
- Logs avoid secrets and unnecessary personal data; credentials use the Windows
  credential store rather than plain-text configuration.
- Domain and application layers remain usable without Qt, SQLAlchemy, network
  clients, or a particular AI provider.
- Core formulas, parsers, repositories, migrations, and view models have
  automated tests. External adapters have contract tests and recorded fixtures
  that contain no personal data.

## 5. Compliance constraint

The requested automatic eBay scraping cannot be assumed to be permissible.
eBay's user terms prohibit automated scraping without prior express permission.
The public Browse API is aimed at active inventory and is not a general
completed-sales feed. Production acquisition therefore requires one of:

1. documented eBay permission and an authorized adapter;
2. an approved/licensed data feed with completed-sale rights; or
3. user-owned imports whose collection and use are lawful.

The browser adapter remains disabled unless the operator explicitly configures
an authorized source. The architecture must not implement CAPTCHA bypass,
fingerprint evasion, proxy rotation, or other access-control circumvention.

## 6. Acceptance criteria for the first commercial release

- Installation, first run, search, analysis, export, backup, and restore work on
  supported Windows versions.
- At least one authorized completed-sale source passes its adapter contract.
- Re-importing identical records creates no duplicate observations or downloads.
- Interrupted synchronization resumes without corruption or silent loss.
- All statistical and recommendation formulas are documented and reproducible.
- Exclusions and normalizations are explainable and reversible.
- A clean database and a migrated prior-version database pass integrity checks.
- The release quality gate passes unit, integration, UI smoke, migration,
  packaging, and security checks.

## 7. Explicitly deferred capabilities

Kleinanzeigen, Amazon, Facebook Marketplace, predictive ML, OCR, barcode and
serial recognition, inventory, accounting, invoicing, shipping, REST APIs,
cloud synchronization, and mobile clients are future bounded contexts. Their
extension points are designed now, but no speculative implementation is added.
