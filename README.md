# MarktWert Desktop

MarktWert is a planned Windows desktop application for analyzing the German
secondary market for computer hardware. It is designed for professional
resellers who need defensible price statistics, liquidity signals, and purchase
recommendations based on completed-sale data.

The repository contains the architecture, runnable application foundation, and
the first completed-sales domain types. Data acquisition and remaining business
features are added as separately tested modules.

## Current scope

- Clean Architecture with MVVM at the Qt boundary
- Python 3.12 project and quality-tool configuration
- Typed application bootstrap and a dark, high-DPI-aware shell
- Exact money, tracked-product criteria, and explainable title classification
- Migrated SQLite storage for tracked products and deduplicated sale observations
- Previewable, transactional CSV/XLSX completed-sales import pipeline
- Responsive FTS5 local search with keyset pagination and recent queries
- Desktop UI for tracked-product criteria, file preview, and imports
- Versioned hardware-title normalization with persisted evidence and confidence
- Accepted-sale statistics, trend, volatility, and seven-day price history
- Architecture, requirements, compliance, and delivery documentation
- Unit and Qt tests for the implemented modules

No completed-listing collector is included yet. A user-enabled, human-paced,
targeted browser adapter is specified with strict stop conditions and no
access-control circumvention; see [`docs/architecture.md`](docs/architecture.md).

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m playwright install chromium
```

Run the desktop shell:

```bash
python -m marktwert
```

Run the quality gate:

```bash
pytest
ruff check .
mypy src
```

## Documentation

- [Product requirements](docs/product-requirements.md)
- [Architecture](docs/architecture.md)
- [Delivery roadmap](docs/delivery-roadmap.md)
- [Completed-sales import format](docs/import-format.md)
- [Hardware title normalization](docs/title-normalization.md)
- [Architecture decisions](docs/adr/0001-clean-architecture-and-mvvm.md)
