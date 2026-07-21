# Architecture

## 1. Architectural style

MarktWert uses Clean Architecture for dependency control and MVVM in the
PySide6 presentation layer. Code is organized by business capability inside
four explicit rings:

```text
presentation (Qt views + view models)
        ↓
application (use cases + ports + DTOs)
        ↓
domain (entities + value objects + policies)

infrastructure implements application/domain ports
and is composed only at the bootstrap boundary.
```

The domain has no imports from Qt, SQLAlchemy, Pandas, Playwright, Requests, or
provider SDKs. UI code never issues SQL or performs network work directly.

This is a modular monolith, not a collection of microservices. It gives a
desktop product clear boundaries and inexpensive in-process calls while keeping
future API/cloud extraction possible.

## 2. Bounded contexts

| Context | Responsibility |
| --- | --- |
| Catalog | Canonical hardware identity and extracted attributes |
| Acquisition | Source capabilities, synchronization, retries, raw provenance |
| Sales | Completed-sale observations, deduplication, enrichment, exclusions |
| Search | Saved queries, filters, favorites, local result projection |
| Analytics | Statistics, time series, comparables, demand and trend |
| Recommendations | Fees, costs, target profit, purchase limits and ROI |
| Deals | Current-offer comparisons and ranked opportunities |
| Watchlists | Schedules, snapshots, thresholds and in-app alerts |
| Reporting | Imports, exports, reports, chart artifacts and backups |
| Settings | User preferences, secrets references and operational policies |

Contexts communicate through typed application services and immutable domain
events. An in-process event dispatcher is sufficient initially. Events are
persisted in an outbox only when a real external integration requires reliable
delivery.

## 3. Package structure

```text
src/marktwert/
├── domain/          # Pure business types, invariants, repository protocols
├── application/     # Commands, queries, DTOs, ports, orchestration
├── infrastructure/  # SQLAlchemy, providers, files, logs, OS integrations
├── presentation/    # PySide6 views, Qt models, view models, resources
├── bootstrap.py     # Composition root; the only dependency-wiring location
└── __main__.py      # Process entry point
```

Each bounded context may repeat these internal patterns when it becomes large;
the code is not split into empty speculative files before behavior exists.

## 4. Domain model

Core identities are opaque typed IDs. Important aggregate boundaries are:

- `SaleObservation`: source identity, original facts, monetary components,
  sale time, listing metadata, provenance, and enrichment state.
- `ProductIdentity`: canonical category and normalized hardware attributes.
- `SavedSearch`: query, filter specification, grouping and display preferences.
- `WatchRule`: saved-search reference, schedule, thresholds and last snapshot.
- `Recommendation`: market estimate plus immutable fee/cost/profit assumptions.

`Money` stores an ISO-4217 currency and integer minor units. `DateRange` and all
timestamps are timezone aware. Unknown data is represented explicitly rather
than replaced with misleading defaults.

Sale records separate three concerns:

1. immutable raw source snapshots for audit and reprocessing;
2. normalized observations used by analytics;
3. user decisions such as exclusion overrides or corrected product matches.

This allows parser and normalizer upgrades without destroying history.

## 5. Data acquisition

`CompletedSalesSource` and `ActiveListingsSource` are separate application
ports because most providers do not offer both datasets or identical semantics.
Every adapter declares capabilities such as date pagination, seller fields,
best-offer accuracy, and request quotas.

An acquisition job follows:

```text
validate query → load cursor → fetch page → validate payload
→ fingerprint raw record → upsert source snapshot
→ map observation → classify/normalize → commit page + cursor
→ publish progress
```

- Idempotency key: `(source_id, external_item_id)`.
- Snapshot identity: item key plus source revision or payload checksum.
- Updates use field-level merge rules; absent incoming values never erase known
  values.
- Retries use bounded exponential backoff with jitter only for transient errors.
- Rate limiting is per provider and persisted where required.
- Quarantine captures malformed records without failing an entire page.

The user-enabled Playwright adapter is deliberately narrow: one visible,
persistent browser session; one page at a time; configurable delays between
page actions and product searches; a bounded 30-day sold-results window; and an
incremental stop once previously collected records are reached. It stops on a
CAPTCHA, access denial, or explicit throttling. It does not spoof fingerprints,
rotate proxies, solve challenges, or bypass other access controls. Playwright
runs in a worker process, never the UI process. Users are warned that targeted
automation can still be restricted by marketplace terms.

Filtering occurs in two stages. Provider-supported query parameters reduce the
result set before download. A versioned local policy then classifies each title
as accepted, excluded, or requiring review. Every non-accepted decision stores
matched evidence. Broad tokens such as `OVP` are not exclusions by themselves.

## 6. Persistence

SQLAlchemy 2.x repositories implement domain protocols. Alembic owns schema
migrations. SQLite is configured with:

- WAL journal mode and foreign keys;
- a busy timeout and short transactions;
- one serialized writer with read-only worker sessions;
- indexes for source identity, sold date, product identity, and common filters;
- FTS5 projections for normalized and original titles;
- page-oriented imports to bound memory and transaction size.

The initial schema will separate `source_records`, `sale_observations`,
`products`, `normalization_runs`, `saved_searches`, `watch_rules`,
`recommendations`, and job state. Raw payload retention is configurable and
compressed; content hashes remain after payload expiry.

Backups use SQLite's online backup API, followed by `PRAGMA integrity_check`.
Restore is staged and verified before atomically replacing the active database.

## 7. Analytics

The analytics service accepts an immutable query specification and repository
projection. SQL performs filtering and basic aggregation. Pandas/NumPy handle
time-series and vectorized analysis only after a bounded projection is loaded.

Rules include:

- use median and robust comparable selection for market-value defaults;
- show mean as descriptive data, not automatically as “real value”;
- do not calculate trend or volatility below documented sample thresholds;
- expose sample size, confidence, exclusions, and window for every result;
- preserve exact money in integer units and convert only at analysis/display
  boundaries;
- cache by data revision plus normalized query and invalidate deterministically.

Matplotlib produces chart models/images outside the UI thread. Qt receives
render-ready results and never performs heavy computation during painting.

## 8. Title normalization

Normalization is a versioned pipeline:

1. Unicode and whitespace normalization;
2. deterministic tokenization and unit normalization;
3. category-specific dictionaries and regex extractors;
4. product catalog matching;
5. optional AI resolution for ambiguous records;
6. confidence scoring and consistency validation.

AI output must satisfy a strict structured schema and cannot overwrite source
facts. Provider, model, prompt/rule version, confidence, latency, and input hash
are recorded. Cached results prevent repeated paid requests. Human overrides
have highest precedence and remain separate from machine output.

## 9. Presentation and concurrency

Qt views contain layout and visual behavior only. View models expose typed state
and commands and depend on application use cases. Read-only table models use
pagination/virtualization rather than materializing the full database.

The concurrency model is deliberately bounded:

- Qt main thread: widgets, signals, and lightweight state transitions;
- `QThreadPool`: cancellable CPU/file/database jobs with per-job sessions;
- dedicated asyncio service thread: asynchronous provider I/O;
- worker process: Playwright or unusually expensive parsing if enabled;
- serialized database write coordinator: protects SQLite from write contention.

Workers emit immutable progress/result/error messages. Shutdown first stops new
jobs, then cancels cooperative work, flushes durable state, and closes resources.

## 10. Configuration, logging, and security

Typed configuration merges packaged defaults, a versioned user TOML file,
environment overrides for development, and secret references. Secrets are held
in the Windows Credential Manager through an infrastructure adapter.

Structured logs include correlation ID, operation, duration, and outcome.
Rotating channels separate application, acquisition, database, and performance
events. Titles and seller data are minimized in logs; credentials and raw
payloads are redacted.

External URLs are allowlisted per adapter. Imports enforce size and schema
limits. Export paths are normalized and writes use temporary files plus atomic
replacement. Dependency and packaged-binary vulnerability scanning belongs in
the release pipeline.

## 11. Extensibility

New marketplaces implement source ports and mapping contracts without changing
analytics. New export formats implement `ReportExporter`. OCR/barcode/serial
recognition produce catalog evidence through dedicated ports. Inventory and
accounting consume stable product, recommendation, and sale concepts through
application APIs rather than database-table coupling.

A future REST API becomes another presentation adapter. Cloud sync requires an
explicit conflict model, encryption, identity, and reliable change log; it is
not approximated with direct SQLite file synchronization.

## 12. Testing and quality gates

- Domain tests: pure, deterministic invariants and formulas.
- Application tests: use cases against fakes, including cancellation/failures.
- Repository tests: real temporary SQLite databases and migration tests.
- Adapter contract tests: shared behavior suite, mocked HTTP, sanitized fixtures.
- UI tests: view-model tests plus a small offscreen Qt smoke suite.
- Property tests: money, parser, deduplication, and import edge cases.
- Performance tests: representative 100k/1m-row projections and startup budgets.

Every module must pass formatting/linting, strict typing, tests, and a runnable
smoke check before the next module begins.
