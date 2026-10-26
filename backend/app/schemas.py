"""Modelos de entrada. Aquí viven las validaciones de la API."""
from datetime import date as date_type
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

Side = Literal["izq", "der", "ambos"]


class WorkoutCreate(BaseModel):
    date: Optional[date_type] = None          # si no se envía, hoy
    routine_id: Optional[int] = None
    bodyweight_kg: Optional[float] = Field(None, gt=0)


class WorkoutFinish(BaseModel):
    duration_seconds: Optional[int] = Field(None, ge=0)
    feeling: Optional[int] = Field(None, ge=1, le=5)
    notes: Optional[str] = None


class SetCreate(BaseModel):
    exercise_id: int
    reps: Optional[int] = Field(None, ge=0, le=200)
    seconds: Optional[int] = Field(None, ge=0)
    side: Side = "ambos"
    extra_weight_kg: float = Field(0, ge=0)
    rpe: Optional[float] = Field(None, ge=1, le=10)
    is_warmup: bool = False

    @model_validator(mode="after")
    def not_empty(self):
        if self.reps is None and self.seconds is None:
            raise ValueError("Una serie necesita reps o segundos")
        return self


class SetUpdate(BaseModel):
    reps: Optional[int] = Field(None, ge=0, le=200)
    seconds: Optional[int] = Field(None, ge=0)
    side: Optional[Side] = None
    extra_weight_kg: Optional[float] = Field(None, ge=0)
    rpe: Optional[float] = Field(None, ge=1, le=10)
    is_warmup: Optional[bool] = None


class NoteIn(BaseModel):
    note: str = Field(min_length=1)
