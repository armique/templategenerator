# ADR 0001: Clean Architecture with MVVM

- Status: Accepted
- Date: 2026-07-21

## Context

The product combines a long-lived desktop UI, marketplace integrations, local
persistence, statistical processing, and future non-desktop interfaces. Qt,
provider payloads, and storage schemas will change at different rates. Coupling
business rules to any one of them would make testing and future extraction
expensive.

## Decision

Use a modular monolith with Clean Architecture dependency direction and MVVM at
the PySide6 boundary.

- Domain code is pure Python and owns business invariants.
- Application code orchestrates use cases and defines external ports.
- Infrastructure implements persistence, provider, file, OS, and AI ports.
- Presentation uses Qt views and view models and calls application use cases.
- `bootstrap.py` is the composition root and wires concrete implementations.

Cross-context access occurs through typed application APIs, not direct table or
widget references.

## Consequences

Business behavior is fast to test without a GUI or database, providers can be
replaced, and a future REST presentation can reuse use cases. The approach adds
mapping between layers and requires discipline around dependency direction.
Those costs are justified by the number of volatile integrations and the
expected product lifetime.

Microservices are rejected for the desktop baseline because deployment,
observability, compatibility, and network failure costs do not improve the
current local product. They remain possible later at stable application ports.
