from __future__ import annotations

import argparse
import os
import sys

from src.mongo_auth.app import create_app
from src.mongo_auth.seed import seed_bulk_users, seed_database


def main() -> None:
    parser = argparse.ArgumentParser(description="MongoDB auth service demo")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("web", help="Run the REST API server")
    subparsers.add_parser("seed", help="Seed demo data into MongoDB")
    bulk_parser = subparsers.add_parser("bulk", help="Generate a large users dataset for streaming demo")
    bulk_parser.add_argument("--target-mb", type=int, default=1024, help="Target dataset size in megabytes")
    bulk_parser.add_argument("--batch-size", type=int, default=250, help="Number of users inserted per batch")

    args = parser.parse_args()

    if args.command == "web":
        app = create_app()
        app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
        return

    if args.command == "seed":
        app = create_app()
        with app.app_context():
            counts = seed_database(app.extensions["mongo_db"])
        print("Seeded collections:")
        for name, count in counts.items():
            print(f"- {name}: {count}")
        return

    if args.command == "bulk":
        app = create_app()
        with app.app_context():
            report = seed_bulk_users(
                app.extensions["mongo_db"],
                target_bytes=args.target_mb * 1024 * 1024,
                batch_size=args.batch_size,
            )
        print("Bulk dataset generated:")
        for name, value in report.items():
            print(f"- {name}: {value}")
        return

    parser.print_help(sys.stderr)


if __name__ == "__main__":
    main()
