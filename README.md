# MarktWert Desktop

MarktWert is a planned Windows desktop application for analyzing the German
secondary market for computer hardware. It is designed for professional
resellers who need defensible price statistics, liquidity signals, and purchase
recommendations based on completed-sale data.

The repository currently contains the architecture and the first runnable
application foundation. Data acquisition and business features will be added as
separately tested modules.

## Current scope

- Clean Architecture with MVVM at the Qt boundary
- Python 3.12 project and quality-tool configuration
- Typed application bootstrap and a dark, high-DPI-aware shell
- Architecture, requirements, compliance, and delivery documentation
- Unit tests for foundation metadata

No completed-listing collector is included yet. Automated eBay access requires
an approved data source or eBay's prior express permission; see
[`docs/architecture.md`](docs/architecture.md).

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
- [Architecture decisions](docs/adr/0001-clean-architecture-and-mvvm.md)
