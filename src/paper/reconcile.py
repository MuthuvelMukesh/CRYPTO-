"""CLI wrapper to run ledger reconciliation: python -m src.paper.reconcile."""

import asyncio

from src.paper.reconciliation import main

if __name__ == "__main__":
    asyncio.run(main())
