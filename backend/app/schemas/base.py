"""Shared Pydantic base so every DTO speaks camelCase on the wire while
the database/models stay snake_case.

- alias_generator=to_camel: `monthly_budget` <-> `monthlyBudget`
- populate_by_name=True: requests may send either spelling
- from_attributes=True: schemas can be built straight from ORM objects
FastAPI serialises responses by alias, so the frontend always sees camelCase.
"""
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )
