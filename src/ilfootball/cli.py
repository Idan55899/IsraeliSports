"""Command line: `ilfootball init-db | check | fetch`."""
from __future__ import annotations

import argparse
import sys

from ilfootball.config import load_settings
from ilfootball.core.http import Fetcher, make_client
from ilfootball.core.ratelimit import HostRateLimiter
from ilfootball.core.raw_store import RawStore
from ilfootball.db.connect import init_db
from ilfootball.quality.checks import run_all


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ilfootball")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db", help="create the DuckDB database and schema")
    sub.add_parser("check", help="run data-quality checks; exit 1 if any issue")
    fetch = sub.add_parser("fetch", help="download one URL into the raw cache")
    fetch.add_argument("--source", required=True)
    fetch.add_argument("--entity", required=True)
    fetch.add_argument("--key", required=True)
    fetch.add_argument("--ext", default="html")
    fetch.add_argument("--refresh", action="store_true")
    fetch.add_argument("url")
    args = parser.parse_args(argv)
    settings = load_settings()

    if args.command == "init-db":
        init_db(settings.db_path).close()
        print(f"database ready: {settings.db_path}")
        return 0

    if args.command == "check":
        con = init_db(settings.db_path)
        issues = run_all(con)
        for issue in issues:
            print(f"[{issue.check}] {issue.match_id}: {issue.detail}")
        print(f"{len(issues)} issue(s)")
        return 1 if issues else 0

    if args.command == "fetch":
        store = RawStore(settings.raw_dir)
        with make_client(settings.user_agent) as client:
            fetcher = Fetcher(store, HostRateLimiter(settings.interval_for), client)
            body = fetcher.get(args.source, args.entity, args.key, args.url, args.ext, args.refresh)
        print(f"{len(body)} bytes -> {store.path_for(args.source, args.entity, args.key, args.ext)}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
