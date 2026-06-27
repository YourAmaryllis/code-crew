---
name: Stack-Python
description: Python service conventions — FastAPI/scripts, directory layout, pytest-bdd runner, ruff linter, and DDD patterns
metadata:
  type: stack
  language: python
  version: "3.12+"
  required-cli:
    - gh
    - python3
    - ruff
    - pre-commit
  detect-files:
    - pyproject.toml
    - setup.py
---

# Stack: Python

## Language & Toolchain

| Item | Tool/Version |
|------|-------------|
| Language | Python 3.12+ |
| Package manager | `uv` (preferred) or `pip` + `venv` |
| Build / run | `uv run` / `uvicorn` (FastAPI) |
| Type check | `mypy` |
| Lint + format | `ruff` |
| Vulnerability scan | `pip-audit` |
| Pre-commit | `ruff`, `mypy` |

---

## Directory Layout

### New Service (FastAPI)

```
services/<service-name>/
  src/
    <context>/
      domain/
        <entity>.py            # aggregate, entities, value objects
        repository.py          # repository ABC (abstract base class)
        events.py              # domain events (dataclasses)
      application/
        <action>_use_case.py   # one file per use case
      infrastructure/
        postgres_<entity>_repo.py  # repository implementation
        <external>_adapter.py       # anti-corruption layer
      api/
        routes/
          <resource>_router.py  # FastAPI router
        schemas.py              # Pydantic request/response schemas
  tests/
    features/
      <domain>/
        <feature>.feature       # Gherkin (QA authors)
    steps/
      <feature>_steps.py        # step definitions (engineer)
    unit/
      test_<entity>.py
  pyproject.toml
  Makefile
```

### Script / AI Tooling

```
scripts/<tool-name>/
  src/
    main.py
    <module>.py
  tests/
    test_<module>.py
  pyproject.toml
```

---

## Test Structure

| Layer | Tool | Command |
|-------|------|---------|
| Unit | `pytest` | `pytest tests/unit/` |
| BDD integration | `pytest-bdd` | `pytest tests/ -k "PROJ-NNN"` |
| All with report | `pytest-html` | `pytest --html=report.html` |
| Coverage | `pytest-cov` | `pytest --cov=src` |

### BDD Step Definition Stub (scaffold output)

```python
# tests/steps/<feature>_steps.py
import pytest
from pytest_bdd import scenarios, given, when, then

scenarios('../features/<domain>/<feature>.feature')

@given('<step text>')
def step_given(context):
    # TODO
    pass

@when('<step text>')
def step_when(context):
    # TODO
    pass

@then('<step text>')
def step_then(context):
    # TODO
    pass
```

---

## DDD Patterns in Python

### Domain Entity

```python
# src/<context>/domain/<entity>.py
from dataclasses import dataclass, field
from typing import List
from uuid import UUID, uuid4

@dataclass
class Order:
    id: UUID = field(default_factory=uuid4)
    status: str = "draft"
    items: List["OrderItem"] = field(default_factory=list)

    def add_item(self, item: "OrderItem") -> None:
        if self.status != "draft":
            raise ValueError("Cannot add items to a non-draft order")
        self.items.append(item)
```

### Value Object

```python
from dataclasses import dataclass

@dataclass(frozen=True)  # frozen = immutable
class Email:
    value: str

    def __post_init__(self):
        if "@" not in self.value:
            raise ValueError(f"Invalid email: {self.value}")
        object.__setattr__(self, "value", self.value.lower().strip())
```

### Repository Interface (domain layer)

```python
# src/<context>/domain/repository.py
from abc import ABC, abstractmethod
from typing import Optional, List
from uuid import UUID

class OrderRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: UUID) -> Optional["Order"]: ...

    @abstractmethod
    async def save(self, order: "Order") -> None: ...
```

### Use Case

```python
# src/<context>/application/create_order_use_case.py
from dataclasses import dataclass
from .domain.order import Order
from .domain.repository import OrderRepository

@dataclass
class CreateOrderUseCase:
    orders: OrderRepository

    async def execute(self, user_id: str) -> Order:
        order = Order()
        await self.orders.save(order)
        return order
```

### Pydantic Schemas (API boundary)

```python
# src/<context>/api/schemas.py
from pydantic import BaseModel, EmailStr

class CreateOrderRequest(BaseModel):
    user_id: str
    items: list[str]

class OrderResponse(BaseModel):
    id: str
    status: str
```

Schemas are at the API boundary only — never leak into domain code.

---

## FastAPI Router Pattern

```python
# src/<context>/api/routes/<resource>_router.py
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/<resource>", tags=["<resource>"])

@router.post("/", response_model=OrderResponse)
async def create_order(
    req: CreateOrderRequest,
    use_case: CreateOrderUseCase = Depends(get_create_order_use_case),
):
    order = await use_case.execute(req.user_id)
    return OrderResponse(id=str(order.id), status=order.status)
```

---

## Makefile Targets

```makefile
.PHONY: test lint typecheck bdd

test:
	pytest tests/unit/

bdd:
	pytest tests/ --html=report.html

lint:
	ruff check src tests

typecheck:
	mypy src

audit:
	pip-audit
```

## API spec — FastAPI auto-generation

FastAPI generates an OpenAPI 3.1 spec automatically from route annotations. No additional tooling needed.

**Export the spec** (run from service root):

```bash
python -m scripts.export_openapi
```

Where `scripts/export_openapi.py` contains:

```python
import json
from pathlib import Path
from app.main import app  # import your FastAPI app

spec = app.openapi()
Path("docs/openapi.json").write_text(json.dumps(spec, indent=2))
```

**Rules:**
- Commit `docs/openapi.json` after every route or schema change
- CI check: `python -m scripts.export_openapi && git diff --exit-code docs/openapi.json`
- All route functions must have `summary=`, `tags=[]`, and typed `response_model=`
- Use `status_code=` explicitly on every route — no implicit 200
- Error responses: add `responses={404: {"model": ErrorResponse}}` to document non-2xx
- Do not use `Any` as a response model — define Pydantic schemas for every response shape

**Pydantic conventions:**
- Request bodies: `class CreateUserRequest(BaseModel):`
- Responses: `class UserResponse(BaseModel):`
- Errors: `class ErrorResponse(BaseModel): code: str; message: str; details: list`

## DB schema — alembic

Install: `pip install alembic`

**Generate a new migration** (auto-detect changes from SQLAlchemy models):

```bash
alembic revision --autogenerate -m "add_user_preferences_table"
```

This writes `migrations/versions/YYYYMMDDHHMMSS_add_user_preferences_table.py`.

**Always review before committing** — autogenerate misses:
- Renamed columns (it sees drop + add, not rename)
- Partial indexes, functional indexes
- CHECK constraints not expressed in SQLAlchemy

**Manual migration** (when autogenerate isn't accurate):

```bash
alembic revision -m "add_index_on_audit_events_created_at"
# then hand-write upgrade() and downgrade() in the generated file
```

**Apply** (CI / human only — never run from crew):

```bash
alembic upgrade head
```

**Rules:**
- Every migration must have both `upgrade()` and `downgrade()`
- Never edit a file that has already been applied in any environment
- `alembic.ini` lives at repo root; `migrations/` is the versions directory
- Commit the migration file alongside the model change in the same PR
- CI check: `alembic check` (fails if there are model changes without a migration)
