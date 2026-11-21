"""
Strict parameter validation/normalisation for the built-in demo strategies.

Local synthetic demo only; not intended for live trading.

Public API:
    normalize_strategy_params(strategy_key, params) -> dict[str, int | float]

Failures raise ValueError (pydantic.ValidationError is a ValueError subclass).
"""
from __future__ import annotations

import math
import re
from decimal import Decimal
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    model_validator,
)

_NUM_RE = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
_MAX_STR_LEN = 64
_MAX_EXPONENT = 1000  # guards against huge-exponent strings like "1e999999999"


def _to_decimal(value: Any) -> Decimal:
    """Convert int/float/numeric-str to a finite Decimal, else raise ValueError."""
    if isinstance(value, bool):
        raise ValueError("boolean values are not accepted")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("value must be finite")
        return Decimal(value)
    if isinstance(value, str):
        text = value.strip()
        if len(text) > _MAX_STR_LEN or not _NUM_RE.fullmatch(text):
            raise ValueError(f"not a valid finite number: {value[:_MAX_STR_LEN]!r}")
        dec = Decimal(text)  # regex excludes nan/inf/underscores
        if dec.is_finite() and dec != 0 and abs(dec.adjusted()) > _MAX_EXPONENT:
            raise ValueError("number magnitude is out of range")
        return dec
    raise ValueError(f"expected a number, got {type(value).__name__}")


def _coerce_int(value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    dec = _to_decimal(value)
    if dec != dec.to_integral_value():
        raise ValueError(f"value must be a whole number, got {value!r}")
    return int(dec)


def _coerce_float(value: Any) -> float:
    dec = _to_decimal(value)
    result = float(dec)
    if not math.isfinite(result):
        raise ValueError("value must be finite")
    return result


# Annotated field types -------------------------------------------------------
_Int = Annotated[int, BeforeValidator(_coerce_int)]
_Float = Annotated[float, BeforeValidator(_coerce_float)]

_Window = Annotated[_Int, Field(ge=1, le=10000)]       # >=1 windows/periods
_Window2 = Annotated[_Int, Field(ge=2, le=10000)]      # >=2 windows
_Pct100 = Annotated[_Float, Field(ge=0, le=100)]       # 0..100 inclusive
_PosMax100 = Annotated[_Float, Field(gt=0, le=100)]    # (0, 100]
_PosMax1 = Annotated[_Float, Field(gt=0, le=1)]        # (0, 1]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class SimpleMAParams(_StrictModel):
    short_window: _Window = 5
    long_window: _Window2 = 20

    @model_validator(mode="after")
    def _check(self) -> "SimpleMAParams":
        if self.short_window >= self.long_window:
            raise ValueError("short_window must be less than long_window")
        return self


class RSIParams(_StrictModel):
    period: _Window = 14
    oversold: _Pct100 = 30.0
    overbought: _Pct100 = 70.0

    @model_validator(mode="after")
    def _check(self) -> "RSIParams":
        if self.oversold >= self.overbought:
            raise ValueError("oversold must be less than overbought")
        return self


class BollingerBandsParams(_StrictModel):
    window: _Window2 = 20
    num_std: _PosMax100 = 2.0


class MACDParams(_StrictModel):
    fast: _Window = 12
    slow: _Window = 26
    signal: _Window = 9

    @model_validator(mode="after")
    def _check(self) -> "MACDParams":
        if self.fast >= self.slow:
            raise ValueError("fast must be less than slow")
        return self


class MomentumParams(_StrictModel):
    window: _Window2 = 10
    threshold: _PosMax100 = 0.02
    stop_loss: _PosMax1 = 0.03


_MODELS: dict[str, type[_StrictModel]] = {
    "simple_ma": SimpleMAParams,
    "rsi": RSIParams,
    "bollinger_bands": BollingerBandsParams,
    "macd": MACDParams,
    "momentum": MomentumParams,
}


def normalize_strategy_params(
    strategy_key: str, params: dict[str, object]
) -> dict[str, int | float]:
    """Validate ``params`` for ``strategy_key`` and return a NEW dict with all
    defaults filled in. Integer fields come back as ``int``; the rest as ``float``.

    Raises ValueError (incl. pydantic.ValidationError) on any invalid input.
    """
    model = _MODELS.get(strategy_key) if isinstance(strategy_key, str) else None
    if model is None:
        raise ValueError(
            f"Unknown strategy {strategy_key!r}. Available: {sorted(_MODELS)}"
        )
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ValueError("params must be a dict")
    return model.model_validate(dict(params)).model_dump()
