# automation/cli.py
import argparse
import sys
import json
import logging
from automation.config import Config
from automation.core import AutomationFramework
from automation.task_queue import TaskQueue


def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")


def main():
    parser = argparse.ArgumentParser(description="Automation Framework CLI")
    parser.add_argument("tasks_file", nargs="?", default="tasks.json", help="path to tasks JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="verbose output")
    parser.add_argument("--api-key", help="GLM API key (overrides env)")
    parser.add_argument("--poll-interval", type=int, default=60, help="quota poll interval (seconds)")
    parser.add_argument("--dry-run", action="store_true", help="simulate only, no API calls")
    args = parser.parse_args()

    setup_logging(args.verbose)

    config = Config.from_env()
    if args.api_key:
        config.api_key = args.api_key
    if not config.api_key:
        print("Error: GLM_API_KEY not set. Use --api-key or set environment variable.")
        sys.exit(1)

    try:
        queue = TaskQueue.from_json(args.tasks_file)
    except FileNotFoundError:
        print(f"Error: tasks file not found: {args.tasks_file}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON: {e}")
        sys.exit(1)

    logging.info(f"Loaded {queue.size()} tasks")

    framework = AutomationFramework(config)
    framework.set_task_queue(queue)

    if args.dry_run:
        logging.info("Dry run mode")
        print("Tasks:")
        for t in queue.tasks:
            print(f"  [{t.level}] {t.id}: {t.title}")
        return

    report = framework.run(poll_interval=args.poll_interval)

    print("\n" + "=" * 50)
    print("Framework Report")
    print("=" * 50)
    print(f"Total: {report['total']}")
    print(f"Completed: {report['completed']}")
    print(f"Failed: {report['failed']}")
    print(f"API calls used: {report['quota_used']}")
    print("-" * 50)
    for task in report["details"]:
        print(f"  [{task['status']}] {task['id']} ({task['budget_used']} calls)")


if __name__ == "__main__":
    main()