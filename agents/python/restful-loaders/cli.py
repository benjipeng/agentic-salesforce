"""
RenoCrypt Data Loader CLI

Loads synthetic CRM data into a Salesforce scratch org using REST API.
Requires metadata to be deployed first: sf project deploy start --source-dir force-app/
"""
from __future__ import annotations

import argparse
import sys

from . import pipeline


def main(argv=None):
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Load RenoCrypt sample data into Salesforce scratch org via REST API.",
        epilog="Note: Ensure custom field metadata is deployed before running this loader.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging output.",
    )

    args = parser.parse_args(argv)

    try:
        results = pipeline.run_full_load()

        # Summary output (only if not already printed by pipeline)
        if not any(hasattr(r, "success") for r in results.values() if r):
            print("\n📊 Load Summary:")
            for name, res in results.items():
                if res is None:
                    if args.verbose:
                        print(f"  {name}: skipped")
                elif hasattr(res, "success"):
                    status = "✓" if res.failed == 0 else "⚠️"
                    print(f"  {status} {name}: {res.success} success, {res.failed} failed")
                elif isinstance(res, list):
                    print(f"  ✓ {name}: {len(res)} records")

        return 0

    except KeyboardInterrupt:
        print("\n\n⚠️  Load interrupted by user")
        return 130
    except Exception as e:
        print(f"\n❌ Error during data load: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
