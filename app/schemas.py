import re
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_RECIPIENTS = 500


class RecipientInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address.")
        return value


class JobCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    event_name: str = Field(min_length=1, max_length=200)
    event_date: date
    recipients: list[RecipientInput] = Field(min_length=1, max_length=MAX_RECIPIENTS)
