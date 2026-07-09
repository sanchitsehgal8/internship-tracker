from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import PipelineRunner, get_default_config, build_pipeline_summary
from .seed_data import ALL_COMPANY_SEEDS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="internship-tracker")
    parser.add_argument("--db", type=Path, help="Override SQLite path")
    parser.add_argument("--outbox", type=Path, help="Override outbox directory")
    parser.add_argument("--alert-to", type=str, help="Alert recipient")
    parser.add_argument("--alert-from", type=str, help="Alert sender")
    parser.add_argument("command", nargs="?", default="run", choices=["run", "summary"])
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config = get_default_config()
    if args.db:
        config.db_path = args.db
    if args.outbox:
        config.outbox_dir = args.outbox
    if args.alert_to:
        config.alert_to_email = args.alert_to
    if args.alert_from:
        config.alert_from_email = args.alert_from
    runner = PipelineRunner(config)
    if args.command == "summary":
        runner.store.initialize()
        print(json.dumps({"stats": runner.store.stats(), "companies": build_pipeline_summary(runner.store)}, indent=2))
        runner.store.close()
        return 0
    stats = runner.run(ALL_COMPANY_SEEDS)
    print(json.dumps(stats, indent=2))
    runner.store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
