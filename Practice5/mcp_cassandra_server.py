from __future__ import annotations

import argparse
import os
import re
import warnings
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

warnings.filterwarnings("ignore", category=DeprecationWarning)


def _patch_gevent() -> bool:
    try:
        from gevent import monkey

        monkey.patch_all()
        return True
    except ImportError:
        return False


GEVENT_PATCHED = _patch_gevent()

from mcp.server.fastmcp import FastMCP


KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "job_market")
MAX_LIMIT = 100
SELECT_RE = re.compile(r"^\s*select\s+", re.IGNORECASE)
BLOCKED_RE = re.compile(r"\b(allow\s+filtering|insert|update|delete|drop|truncate|alter|create)\b", re.IGNORECASE)

app = FastMCP(
    "practice5-cassandra",
    instructions=(
        "Read-only MCP server for Practice5 Apache Cassandra job market data. "
        "Use primary-key queries against the job_market keyspace."
    ),
)


def _connection_class():
    if GEVENT_PATCHED:
        from cassandra.io.geventreactor import GeventConnection

        return GeventConnection
    return None


def _session():
    connection_class = _connection_class()

    from cassandra.auth import PlainTextAuthProvider
    from cassandra.cluster import Cluster
    from cassandra.policies import DCAwareRoundRobinPolicy

    hosts = [host.strip() for host in os.getenv("CASSANDRA_HOSTS", "127.0.0.1").split(",")]
    port = int(os.getenv("CASSANDRA_PORT", "9042"))
    username = os.getenv("CASSANDRA_USERNAME")
    password = os.getenv("CASSANDRA_PASSWORD")
    protocol_version = int(os.getenv("CASSANDRA_PROTOCOL_VERSION", "5"))
    local_dc = os.getenv("CASSANDRA_LOCAL_DC", "datacenter1")
    auth_provider = PlainTextAuthProvider(username=username, password=password) if username and password else None
    cluster = Cluster(
        contact_points=hosts,
        port=port,
        auth_provider=auth_provider,
        connection_class=connection_class,
        load_balancing_policy=DCAwareRoundRobinPolicy(local_dc=local_dc),
        protocol_version=protocol_version,
    )
    session = cluster.connect(KEYSPACE)
    return cluster, session


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "date") and not isinstance(getattr(value, "date"), int):
        return value.date().isoformat()
    if isinstance(value, (set, tuple)):
        return sorted(str(item) for item in value)
    return str(value) if not isinstance(value, (str, int, float, bool, type(None))) else value


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {name: _json_value(getattr(row, name)) for name in row._fields}


def _fetch(cql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    cluster, session = _session()
    try:
        rows = session.execute(cql, params)
        return [_row_to_dict(row) for row in rows]
    finally:
        cluster.shutdown()


def _limit(limit: int) -> int:
    if limit < 1:
        raise ValueError("limit must be positive")
    return min(limit, MAX_LIMIT)


@app.resource("cassandra://practice5/schema")
def schema_resource() -> str:
    path = Path(__file__).resolve().parent / "cassandra" / "schema.cql"
    return path.read_text(encoding="utf-8")


@app.tool()
def cassandra_health() -> dict[str, Any]:
    """Check Cassandra connectivity and return the active keyspace."""
    rows = _fetch("SELECT keyspace_name FROM system_schema.keyspaces WHERE keyspace_name = %s", (KEYSPACE,))
    return {"ok": bool(rows), "keyspace": KEYSPACE, "rows": rows}


@app.tool()
def list_tables() -> list[str]:
    """List tables in the Practice5 Cassandra keyspace."""
    rows = _fetch("SELECT table_name FROM system_schema.tables WHERE keyspace_name = %s", (KEYSPACE,))
    return sorted(row["table_name"] for row in rows)


@app.tool()
def describe_table(table_name: str) -> list[dict[str, Any]]:
    """Describe columns and primary key positions for a table."""
    table_name = table_name.strip().lower()
    rows = _fetch(
        """
        SELECT column_name, kind, position, type
        FROM system_schema.columns
        WHERE keyspace_name = %s AND table_name = %s
        """,
        (KEYSPACE, table_name),
    )
    return sorted(rows, key=lambda row: (str(row["kind"]), int(row["position"]), row["column_name"]))


@app.tool()
def vacancies_by_profession(profession: str, limit: int = 10) -> list[dict[str, Any]]:
    """Read vacancies by profession using vacancies_by_profession primary key."""
    return _fetch(
        "SELECT * FROM vacancies_by_profession WHERE profession = %s LIMIT %s",
        (profession.strip().lower(), _limit(limit)),
    )


@app.tool()
def recent_vacancies(limit: int = 10) -> list[dict[str, Any]]:
    """Read all recent vacancies using vacancies_feed primary key."""
    return _fetch(
        "SELECT * FROM vacancies_feed WHERE feed_name = %s LIMIT %s",
        ("all", _limit(limit)),
    )


@app.tool()
def vacancies_by_region(country: str, region: str, limit: int = 10) -> list[dict[str, Any]]:
    """Read vacancies by country and region using vacancies_by_region primary key."""
    return _fetch(
        "SELECT * FROM vacancies_by_region WHERE country = %s AND region = %s LIMIT %s",
        (country.strip().lower(), region.strip().lower(), _limit(limit)),
    )


@app.tool()
def vacancies_by_remote(remote: bool = True, limit: int = 10) -> list[dict[str, Any]]:
    """Read vacancies by remote flag using vacancies_by_remote primary key."""
    return _fetch(
        "SELECT * FROM vacancies_by_remote WHERE remote = %s LIMIT %s",
        (remote, _limit(limit)),
    )


@app.tool()
def vacancies_by_employment_type(employment_type: str, limit: int = 10) -> list[dict[str, Any]]:
    """Read vacancies by employment type using vacancies_by_employment_type primary key."""
    return _fetch(
        "SELECT * FROM vacancies_by_employment_type WHERE employment_type = %s LIMIT %s",
        (employment_type.strip().lower(), _limit(limit)),
    )


@app.tool()
def vacancies_by_experience_level(experience_level: str, limit: int = 10) -> list[dict[str, Any]]:
    """Read vacancies by experience level using vacancies_by_experience_level primary key."""
    return _fetch(
        "SELECT * FROM vacancies_by_experience_level WHERE experience_level = %s LIMIT %s",
        (experience_level.strip().lower(), _limit(limit)),
    )


@app.tool()
def vacancies_by_city(country: str, city: str, limit: int = 10) -> list[dict[str, Any]]:
    """Read vacancies by country and city using vacancies_by_city primary key."""
    return _fetch(
        "SELECT * FROM vacancies_by_city WHERE country = %s AND city = %s LIMIT %s",
        (country.strip().lower(), city.strip().lower(), _limit(limit)),
    )


@app.tool()
def region_stats(country: str, region: str) -> list[dict[str, Any]]:
    """Read region statistics using region_stats_by_key primary key."""
    return _fetch(
        "SELECT * FROM region_stats_by_key WHERE country = %s AND region = %s LIMIT 1",
        (country.strip().lower(), region.strip().lower()),
    )


@app.tool()
def safe_select(cql: str, limit: int = 20) -> list[dict[str, Any]]:
    """Run a read-only SELECT. Mutations and ALLOW FILTERING are rejected."""
    if not SELECT_RE.search(cql) or BLOCKED_RE.search(cql) or ";" in cql.strip().rstrip(";"):
        raise ValueError("Only a single read-only SELECT without ALLOW FILTERING is allowed")
    cleaned = cql.strip().rstrip(";")
    if " limit " not in cleaned.lower():
        cleaned = f"{cleaned} LIMIT {_limit(limit)}"
    return _fetch(cleaned)


def smoke_test() -> None:
    print(cassandra_health())
    print(list_tables())
    print(recent_vacancies(2))
    print(vacancies_by_profession("python developer", 2))
    print(vacancies_by_employment_type("full-time", 2))
    print(vacancies_by_city("russia", "moscow", 2))
    print(region_stats("russia", "moscow"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Practice5 Cassandra MCP server")
    parser.add_argument("--smoke-test", action="store_true", help="Run direct checks without starting MCP stdio")
    args = parser.parse_args()
    if args.smoke_test:
        smoke_test()
    else:
        app.run(transport="stdio")
