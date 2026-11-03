"""JSON codec of D records stored in JSONB payload columns."""
from __future__ import annotations

import collections.abc
import dataclasses
import types
import typing
from types import MappingProxyType
from typing import Any


def encode_record(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {field.name: encode_record(getattr(value, field.name)) for field in dataclasses.fields(value) if field.init}
    if isinstance(value, collections.abc.Mapping):
        return {str(key): encode_record(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode_record(item) for item in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise TypeError(f'unsupported value in record: {type(value).__name__}')


def decode_record(tp: Any, value: Any) -> Any:
    origin = typing.get_origin(tp)
    if origin is typing.Union or origin is types.UnionType:
        arms = [arm for arm in typing.get_args(tp) if arm is not type(None)]
        if value is None:
            return None
        if len(arms) != 1:
            raise TypeError(f'unsupported union: {tp!r}')
        return decode_record(arms[0], value)
    if tp is Any or tp is object:
        return value
    if isinstance(tp, type) and dataclasses.is_dataclass(tp):
        hints = typing.get_type_hints(tp)
        # PRS-LAYOUT-PLAN: a field added later with a default (ProductionPlan.layout_choice) may be absent from a record stored before it.
        return tp(**{
            field.name: decode_record(hints[field.name], value[field.name]) for field in dataclasses.fields(tp)
            if field.init and (field.name in value or (field.default is dataclasses.MISSING and field.default_factory is dataclasses.MISSING))
        })
    if origin is tuple:
        return tuple(decode_record(typing.get_args(tp)[0], item) for item in value)
    if origin is collections.abc.Mapping or origin is dict:
        args = typing.get_args(tp)
        item_type = args[1] if len(args) == 2 else object
        return MappingProxyType({key: decode_record(item_type, item) for key, item in value.items()})
    if tp is float:
        return float(value)
    return value