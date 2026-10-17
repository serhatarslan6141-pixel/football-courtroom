"""Run with --live to authorize at most one billable model request."""
import argparse
import asyncio
import logging

from dotenv import load_dotenv

from .foundry import FoundryConnection, FoundryUnavailable, ROOT


def main(argv=None):
    parser = argparse.ArgumentParser(description='Controlled backend-only Foundry connection test.')
    parser.add_argument('--live', action='store_true', help='Authorize ONE potentially billable request (no retries).')
    args = parser.parse_args(argv)
    if not args.live:
        print('No request sent. Use --live to authorize one potentially billable connection test.')
        return 0
    # Never print provider payloads, model text, endpoint, credentials or tracebacks.
    previous_logging_disable = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        load_dotenv(ROOT / '.env', override=False, interpolate=False)
        asyncio.run(FoundryConnection().test_connection(single_attempt=True))
    except FoundryUnavailable as exc:
        print(f'Connection test failed: {exc}')
        return 1
    finally:
        logging.disable(previous_logging_disable)
    print('Foundry connection verified: expected model response received. One live request sent.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
