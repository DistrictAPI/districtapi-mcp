"""
districtapi MCP server — exposes US school district and school data as MCP tools.

Configure with environment variable:
  DISTRICTAPI_KEY=your_api_key

Run via uvx:
  uvx districtapi-mcp
"""

import os
import re
import httpx
from mcp.server.fastmcp import FastMCP

BASE_URL = os.environ.get("DISTRICTAPI_BASE_URL", "https://api.districtapi.dev")
API_KEY = os.environ.get("DISTRICTAPI_KEY", "")

mcp = FastMCP(
    "districtapi",
    instructions=(
        "Use these tools to look up US public school districts and schools. "
        "Data is sourced from NCES Common Core of Data (CCD), updated annually. "
        "The most powerful tool is lookup_district_by_address — pass any US street "
        "address to get the district serving that location."
    ),
)


def _headers() -> dict:
    if not API_KEY:
        raise ValueError(
            "DISTRICTAPI_KEY environment variable is not set. "
            "Get a free API key at https://districtapi.dev"
        )
    return {"X-API-Key": API_KEY, "Accept": "application/json"}


def _get(path: str, params: dict = None) -> dict:
    with httpx.Client(base_url=BASE_URL, headers=_headers(), timeout=10) as client:
        response = client.get(path, params=params)
        response.raise_for_status()
        return response.json()


# Identifiers below are interpolated into the outbound request path. httpx
# resolves a path-absolute string against the base URL and collapses ".."
# during normalisation, so an unvalidated id can redirect the request to a
# different path on the same host while still carrying the caller's API key
# (reported by Syed Anas Mohiuddin, Sept 2026). "?" and "#" would likewise
# inject a query string or fragment, which that report did not cover.
#
# Allowlist rather than block dangerous characters: every identifier in the
# upstream data is alphanumeric with optional "-"/"_" — verified against every
# row (LEA ids 7 digits, school ids 12, FSCS ids 6, outlet ids 10, station ids
# 11-19; none outside this set) — so a blocklist can only be less complete.
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _safe_id(value: str, field: str) -> str:
    """Return the identifier unchanged, or raise if it could escape the path."""
    if not _SAFE_ID.match(value or ""):
        raise ValueError(
            f"{field} must contain only letters, digits, '-' or '_' "
            f"(got {value!r})"
        )
    return value


# ---------------------------------------------------------------------------
# District tools
# ---------------------------------------------------------------------------

@mcp.tool()
def lookup_district_by_address(address: str) -> dict:
    """
    Find the public school district serving a US street address.

    Returns the district name, NCES ID, state, enrollment, school count,
    per-pupil expenditure, and demographic breakdown.

    Args:
        address: Full US street address, e.g. "1600 Pennsylvania Ave, Austin, TX"
    """
    return _get("/v1/districts", params={"address": address})


@mcp.tool()
def get_district(nces_id: str) -> dict:
    """
    Get full profile for a school district by its NCES LEA ID.

    Args:
        nces_id: 7-digit NCES Local Education Agency ID, e.g. "4807380"
    """
    return _get(f"/v1/districts/{_safe_id(nces_id, 'nces_id')}")


@mcp.tool()
def search_districts(name: str, state: str = "") -> dict:
    """
    Search for school districts by name, optionally filtered by state.

    Args:
        name:  Full or partial district name, e.g. "Austin" or "Austin ISD"
        state: Two-letter state code to narrow results, e.g. "TX" (optional)
    """
    params = {"name": name}
    if state:
        params["state"] = state.upper()
    return _get("/v1/districts/search", params=params)


@mcp.tool()
def get_district_schools(nces_id: str) -> dict:
    """
    List all schools in a district.

    Args:
        nces_id: 7-digit NCES LEA ID of the district
    """
    return _get(f"/v1/districts/{_safe_id(nces_id, 'nces_id')}/schools")


# ---------------------------------------------------------------------------
# School tools
# ---------------------------------------------------------------------------

@mcp.tool()
def get_school(nces_id: str) -> dict:
    """
    Get full profile for a school by its NCES school ID.

    Args:
        nces_id: 12-digit NCES school ID
    """
    return _get(f"/v1/schools/{_safe_id(nces_id, 'nces_id')}")


@mcp.tool()
def find_schools_near_address(address: str, radius_miles: float = 5.0) -> dict:
    """
    Find public schools within a radius of a US street address.

    Args:
        address:      Full US street address
        radius_miles: Search radius in miles (default 5.0, max 25.0)
    """
    return _get("/v1/schools", params={"address": address, "radius_miles": radius_miles})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    mcp.run()


if __name__ == "__main__":
    main()
