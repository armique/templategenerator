# Incremental Delivery Roadmap

Each numbered increment is independently runnable, tested, documented, and
committed. A later increment starts only after the preceding quality gate passes.

1. **Application foundation**  
   Package layout, bootstrap, dark high-DPI shell, configuration conventions,
   logging setup, test/lint/type tooling, and architecture documentation.

2. **Collection criteria and sales domain**
   Exact money, tracked-product criteria, explainable title classification,
   time ranges, source provenance, sale aggregate, and domain tests.

3. **SQLite persistence**  
   SQLAlchemy mappings, Alembic, repositories, WAL/write coordination,
   deduplication/enrichment rules, integrity checks, and migration tests.

4. **Import source**  
   CSV/Excel schema detection, preview, validation, quarantine report,
   idempotent page imports, progress/cancellation, and integration tests. This
   creates a lawful end-to-end data path before network acquisition.

5. **Search workspace**  
   Query/filter specifications, local FTS search, paged Qt table model, recent
   searches, favorites, and responsive view-model tests.

6. **Tracked-product and import workspace**
   Add/edit/disable/remove collection profiles, full criteria editor, bounded
   import preview, transactional execution, and asynchronous Qt integration.

7. **Rule-based normalization**
   Category dictionaries, hardware attribute extractors, exclusion rules,
   confidence/evidence, user overrides, and fixture-based tests.

8. **Core statistics and history**
   Robust comparable selection, descriptive metrics, time windows, caching,
   price-history visualization, and validated numerical tests.

9. **Purchase recommendations**
   Fee/cost policies, target-profit calculations, assumptions UI, persistence,
   reproducible reports, and boundary/property tests.

10. **Targeted completed-sales adapters**
   Add provider capabilities, rate limits, cursor sync, retries, raw provenance,
   contract tests, and operational diagnostics. Support an approved API/feed
   source and the explicitly user-enabled visible-browser mode described in the
   architecture, without access-control circumvention.

11. **Advanced charts and market scores**
    Distribution/group charts, trend and volatility, demand/liquidity formulas,
    confidence labels, and performance tests.

12. **Watchlists and scheduler**
    Durable schedules, snapshots, in-app alerts, missed-run recovery, and
    controlled shutdown.

13. **Deal finder**
    Authorized active-listing adapter, comparable matching, net-margin ranking,
    explainability, and stale-data safeguards.

14. **AI-assisted normalization**
    Provider-neutral structured output, privacy controls, deterministic cache,
    model/rule provenance, budget controls, and fallback behavior.

15. **Reporting, backup, and restore**
    CSV/JSON/Excel/PDF/PNG outputs, report provenance, online verified backups,
    staged restore, and failure tests.

16. **Windows release engineering**
    Signed packaging, clean-machine install/upgrade tests, crash reporting
    policy, accessibility pass, security review, and release documentation.

Future marketplace, inventory, accounting, OCR, API, cloud, and mobile contexts
start only after their contracts and compliance requirements are separately
specified.
