from __future__ import annotations

import argparse
import os
import sys

from src.job_market.app import create_app
from src.job_market.memory_repository import InMemoryJobMarketRepository
from src.job_market.seed import seed_repository


def build_repository(backend: str):
    backend = backend.lower().strip()
    if backend == "memory":
        return InMemoryJobMarketRepository()
    if backend == "cassandra":
        return None
    raise SystemExit(f"Unknown backend: {backend}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Job market statistics demo")
    parser.add_argument(
        "--backend",
        default=os.getenv("JOB_MARKET_BACKEND", "memory"),
        choices=["memory", "cassandra"],
        help="Storage backend to use",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("web", help="Run the REST API server")
    subparsers.add_parser("seed", help="Seed demo data into the selected backend")
    subparsers.add_parser("demo", help="Print a short demo of the repository queries")

    args = parser.parse_args()
    repository = build_repository(args.backend)

    if args.command == "web":
        app = create_app(repository=repository, backend=args.backend)
        app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
        return

    if args.command == "seed":
        if repository is None:
            app = create_app(repository=None, backend=args.backend)
            repository = app.extensions["job_market_repository"]
        counts = seed_repository(repository)
        print("Seeded objects:")
        for name, count in counts.items():
            print(f"- {name}: {count}")
        return

    if args.command == "demo":
        if repository is None:
            app = create_app(repository=None, backend=args.backend)
            repository = app.extensions["job_market_repository"]
        seed_repository(repository)
        from src.job_market.services import now_utc

        print(f"Demo time: {now_utc().isoformat()}")
        print("Vacancies by profession 'python developer':")
        for vacancy in repository.list_vacancies_by_profession("python developer", limit=3):
            print(f"- {vacancy.title} at {vacancy.employer_name}")
        print("Region stats for russia / moscow:")
        stats = repository.get_region_stats("russia", "moscow")
        print(stats)
        return

    parser.print_help(sys.stderr)


if __name__ == "__main__":
    main()
