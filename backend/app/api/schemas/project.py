"""Project API schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200, examples=["Rika"])
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("name must not be blank")
        return name

    @field_validator("description")
    @classmethod
    def _clean_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class ProjectUpdate(BaseModel):
    """Partial update.

    Omitted fields are left alone; an explicit ``null`` description clears it.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        name = value.strip()
        if not name:
            raise ValueError("name must not be blank")
        return name

    @field_validator("description")
    @classmethod
    def _clean_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def _at_least_one_field(self) -> ProjectUpdate:
        if not self.model_fields_set:
            raise ValueError("provide at least one of: name, description")
        return self


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    settings: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ProjectList(BaseModel):
    items: list[ProjectRead]
    total: int
    limit: int
    offset: int
