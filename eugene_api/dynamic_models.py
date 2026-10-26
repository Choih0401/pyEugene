"""
Builds one Pydantic model per TR code / Real ID from the parsed catalog, so
every generated route gets a request/response schema Swagger can render -
instead of one generic `Dict[str, str]` endpoint for all ~150 codes.
"""
from typing import List, Optional, Type

from pydantic import BaseModel, Field, create_model

from eugene_api.catalog import FieldSpec, RealSpec, TranSpec


def _field_tuple(f: FieldSpec, required: bool):
    default = ... if required else ""
    return (str, Field(default, description=f"{f.name} ({f.size}) - {f.description}".strip(" -")))


def build_tran_input_model(spec: TranSpec) -> Type[BaseModel]:
    fields = {f.item: _field_tuple(f, required=False) for f in spec.input}
    return create_model(f"{spec.code}_Input", **fields)  # type: ignore[call-overload]


def _record_model(name: str, fields: List[FieldSpec]) -> Type[BaseModel]:
    model_fields = {
        f.item: (Optional[str], Field(default=None, description=f"{f.name} ({f.size}) - {f.description}".strip(" -")))
        for f in fields
    }
    return create_model(name, **model_fields)  # type: ignore[call-overload]


def build_tran_output_model(spec: TranSpec) -> Type[BaseModel]:
    kwargs = {}
    if spec.output_single:
        single_model = _record_model(f"{spec.code}_OutRec1", spec.output_single)
        kwargs["OutRec1"] = (Optional[single_model], None)
    if spec.output_multi:
        multi_model = _record_model(f"{spec.code}_OutRec2Row", spec.output_multi)
        kwargs["OutRec2"] = (Optional[List[multi_model]], None)
    return create_model(f"{spec.code}_Output", **kwargs)  # type: ignore[call-overload]


def build_real_output_model(spec: RealSpec) -> Type[BaseModel]:
    return _record_model(f"Real_{spec.code}_Output", spec.output)
