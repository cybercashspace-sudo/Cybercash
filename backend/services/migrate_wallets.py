import asyncio
import logging
from sqlalchemy import select
from backend.database import AsyncSessionLocal
from backend.models import User, Wallet

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def ensure_all_users_have_wallets():
    """
    Migration script to provision wallets for users who are missing one.
    Prevents errors in TransactionEngine caused by stricter wallet enforcement.
    """
    async with AsyncSessionLocal() as db:
        # Select user IDs where no wallet exists (outer join)
        stmt = select(User.id).outerjoin(Wallet, User.id == Wallet.user_id).where(Wallet.id == None)
        result = await db.execute(stmt)
        user_ids = result.scalars().all()

        if not user_ids:
            logger.info("Consistency Check: All users already have wallets. No migration needed.")
            return

        logger.info(f"Found {len(user_ids)} users without wallets. Creating GHS wallets...")
        for user_id in user_ids:
            db.add(Wallet(user_id=user_id, currency="GHS", balance=0.0))
        
        await db.commit()
        logger.info("Data Integrity Migration successful.")

if __name__ == "__main__":
    asyncio.run(ensure_all_users_have_wallets())