#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx",
#     "mousebender",
#     "packaging",
#     "uv",
# ]
# ///
from __future__ import annotations
from enum import Enum, auto
import packaging.utils
import subprocess
import re
import httpx
from mousebender.simple import ProjectDetails_1_3 as ProjectDetails

PKG_RE = re.compile(r'^(\w+)==.*', re.MULTILINE)

def main() -> None:
    reqs = subprocess.check_output(["uv", "export", "--output-file=-", '--all-groups', '--no-dev'], text=True)
    deps = [hit.group(1) for hit in PKG_RE.finditer(reqs)]
    overall = FreeThreadingSupport.PURE_PYTHON
    for dep in deps:
        status = f"{dep}: "
        try:
            match dep_support := check_dep(dep):
                case FreeThreadingSupport.FT_WHEEL:
                    status += "🧵"
                case FreeThreadingSupport.PURE_PYTHON:
                    status += "🐍"
                case _:
                    status += "🐌"
            overall = max(overall, dep_support)
        except Exception as e:
            status += f"💥 ({type(e).__qualname__}: {e})"
            all_threading = False
        print(status)
    if overall is FreeThreadingSupport.NO_SUPPORT:
        print("Some dependencies don't have free-threading support.")
    else:
        print("All dependencies have freed the threading.")

class FreeThreadingSupport(Enum):
    PURE_PYTHON = auto()
    FT_WHEEL = auto()
    NO_SUPPORT = auto()

    def __lt__(self, other: FreeThreadingSupport) -> bool:
        return self.value < other.value

def check_dep(pkg: str) -> FreeThreadingSupport:
    normalized = packaging.utils.canonicalize_name(pkg)
    resp = httpx.get(f"https://pypi.org/simple/{normalized}/", headers={"Accept": "application/vnd.pypi.simple.v1+json"})
    resp.raise_for_status()
    data: ProjectDetails = resp.json()
    has_binary_wheel = False
    has_free_threaded = False
    for f in data["files"]:
        if f.get("yanked"):
            continue
        filename = f["filename"]
        if filename.endswith('.whl'):
            name, version, btag, tags = packaging.utils.parse_wheel_filename(filename)
            for tag in tags:
                if tag.abi != "none":
                    has_binary_wheel = True
                if tag.abi.endswith('t'):
                    has_free_threaded = True
    match (has_binary_wheel, has_free_threaded):
        case (False, _):
            return FreeThreadingSupport.PURE_PYTHON
        case (_, True):
            return FreeThreadingSupport.FT_WHEEL
        case _:
            return FreeThreadingSupport.NO_SUPPORT

if __name__ == "__main__":
    main()
