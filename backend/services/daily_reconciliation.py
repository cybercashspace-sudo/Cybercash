import asyncio
import logging
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.database import async_session
from backend.services.reconciliation_service import reconcile_all_wallets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger("reconciliation_script")

async def main():
    """
    Standalone script to run the daily wallet reconciliation.
    Execution: python -m backend.scripts.daily_reconciliation
    """
    logger.info("Starting wallet reconciliation batch...")
    
    try:
        async with async_session() as db:
            report = await reconcile_all_wallets(db)
            
            logger.info("Reconciliation Complete.")
            logger.info(f"  Processed: {report['total_users']} users")
            logger.info(f"  Verified:  {report['verified_count']}")
            logger.info(f"  Mismatched: {report['mismatch_count']}")
            logger.info(f"  Frozen:    {report['locked_count']}")
            
            if report['mismatch_count'] > 0:
                logger.error("ALARM: Discrepancies found! Check audit logs for WALLET_RECONCILIATION_MISMATCH.")
    except Exception as e:
        logger.error(f"Reconciliation script failed: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())