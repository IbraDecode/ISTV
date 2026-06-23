import json
from datetime import datetime
from typing import Any
from pydantic import BaseModel, field_validator


class Pagination(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int


def _ensure_dict(v: Any) -> Any:
    if isinstance(v, str):
        try:
            return json.loads(v)
        except (json.JSONDecodeError, TypeError):
            return {}
    return v if v else {}


class ChannelOut(BaseModel):
    id: int
    tvg_id: str
    name: str
    logo: str
    group_name: str | None = None
    url: str
    stream_type: str
    has_drm: bool
    drm_info: dict | None = None
    headers: dict = {}
    country: str
    is_active: bool

    @field_validator("headers", "drm_info", mode="before")
    @classmethod
    def parse_json(cls, v: Any) -> Any:
        return _ensure_dict(v)

    model_config = {"from_attributes": True}


class CategoryOut(BaseModel):
    id: int
    name: str
    channel_count: int


class ProgramOut(BaseModel):
    id: int
    channel_tvg_id: str
    title: str
    description: str
    start_time: datetime
    end_time: datetime
    category: str


class NowNextOut(BaseModel):
    now: ProgramOut | None = None
    next: ProgramOut | None = None


class ChannelWithEpgOut(ChannelOut):
    epg_now: ProgramOut | None = None
    epg_next: ProgramOut | None = None


class StatsOut(BaseModel):
    total_channels: int
    total_categories: int
    total_epg_programs: int
    channels_by_type: dict
    channels_by_drm: dict
    top_categories: list[CategoryOut]


class ApiResponse(BaseModel):
    success: bool = True
    message: str | None = None
    data: object | None = None
    pagination: Pagination | None = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    code: int
