"""Typed inputs and results for the repository tools."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class FileEntry(BaseModel):
    path: str
    size_bytes: int


class ListFilesResult(BaseModel):
    ok: Literal[True] = True
    prefix: str
    files: list[FileEntry]
    truncated: bool


class ReadFileResult(BaseModel):
    ok: Literal[True] = True
    path: str
    start_line: int
    end_line: int
    total_lines: int
    content: str = Field(description="Numbered lines, 'N| text'")


class SearchHit(BaseModel):
    path: str
    line: int
    text: str


class SearchResult(BaseModel):
    ok: Literal[True] = True
    pattern: str
    hits: list[SearchHit]
    files_searched: int
    truncated: bool
