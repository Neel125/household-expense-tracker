"""Ledger & Card backend application package (MVC layout).

Layers (outer -> inner):
    controllers/  FastAPI routers — HTTP only, no business rules
    services/     business logic, orchestration, invariants
    repositories/ data access — the only layer that touches the DB session
    models/       SQLModel tables (the persistent domain model)
    schemas/      Pydantic request/response DTOs (the "view" contracts)
    core/         cross-cutting concerns: config, db engine, security, deps

Each layer depends only on the ones beneath it, which keeps the
dependency direction acyclic (Dependency Inversion / clean layering).
"""
