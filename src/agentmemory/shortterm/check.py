"""Validate short-term memory markdown files."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

MAX_LINES = 80
MAX_SESSION_LOG_ENTRIES = 15


@dataclass
class CheckResult:
    """Result from checking a single memory file."""
    path: str
    name: str
    line_count: int
    session_entries: int
    over_limit: bool
    session_warn: bool
    fixed: bool = False
    new_line_count: Optional[int] = None

    @property
    def status(self) -> str:
        if self.over_limit:
            return "FAIL"
        return "PASS"


def count_session_log_entries(lines: List[str]) -> int:
    """Count dated session log entries in a memory file."""
    in_session_log = False
    count = 0
    for line in lines:
        if re.match(r"^## Session Log", line):
            in_session_log = True
            continue
        if in_session_log:
            if re.match(r"^## ", line):
                break
            if re.match(r"^- \[", line):
                count += 1
    return count


def prune_session_log(lines: List[str], max_entries: int) -> List[str]:
    """Remove oldest session log entries (at bottom, newest-first)."""
    session_start = None
    session_end = None
    entry_indices: List[int] = []

    for i, line in enumerate(lines):
        if re.match(r"^## Session Log", line):
            session_start = i
            continue
        if session_start is not None and session_end is None:
            if re.match(r"^## ", line):
                session_end = i
                break
            if re.match(r"^- \[", line):
                entry_indices.append(i)

    if session_start is None:
        return lines

    if session_end is None:
        session_end = len(lines)

    if len(entry_indices) <= max_entries:
        return lines

    lines_to_remove = set(entry_indices[max_entries:])
    return [line for i, line in enumerate(lines) if i not in lines_to_remove]


def check_file(path: str, fix: bool = False) -> CheckResult:
    """Check a single memory file for size limits."""
    name = os.path.basename(path)
    with open(path, "r") as f:
        lines = f.readlines()

    line_count = len(lines)
    session_entries = count_session_log_entries(lines)
    over_limit = line_count > MAX_LINES
    session_warn = session_entries > MAX_SESSION_LOG_ENTRIES

    result = CheckResult(
        path=path,
        name=name,
        line_count=line_count,
        session_entries=session_entries,
        over_limit=over_limit,
        session_warn=session_warn,
    )

    if fix and (over_limit or session_warn):
        new_lines = list(lines)

        if session_entries > MAX_SESSION_LOG_ENTRIES:
            new_lines = prune_session_log(new_lines, MAX_SESSION_LOG_ENTRIES)

        if len(new_lines) > MAX_LINES:
            excess = len(new_lines) - MAX_LINES
            target = max(MAX_SESSION_LOG_ENTRIES - excess, 5)
            new_lines = prune_session_log(new_lines, target)

        if len(new_lines) != len(lines):
            with open(path, "w") as f:
                f.writelines(new_lines)
            result.fixed = True
            result.new_line_count = len(new_lines)
            result.over_limit = len(new_lines) > MAX_LINES
            result.session_warn = (
                count_session_log_entries(new_lines) > MAX_SESSION_LOG_ENTRIES
            )

    return result


def check_directory(
    memory_dir: str,
    fix: bool = False,
) -> List[CheckResult]:
    """Check all .md files in a memory directory."""
    pattern = os.path.join(memory_dir, "*.md")
    import glob as _glob

    files = sorted(_glob.glob(pattern))
    return [check_file(path, fix=fix) for path in files]
