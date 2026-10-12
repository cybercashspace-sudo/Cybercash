import asyncio
import logging
from sqlalchemy import select
from backend.database import AsyncSessionLocal
from backend.models import User, Wallet

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def ensure_all_users_have_wallets():
    """
    Audit wallet coverage without creating zero-balance wallets for existing users.
    """
    async with AsyncSessionLocal() as db:
        # Select user IDs where no wallet exists (outer join)
        stmt = select(User.id).outerjoin(Wallet, User.id == Wallet.user_id).where(Wallet.id == None)
        result = await db.execute(stmt)
        user_ids = result.scalars().all()

        if not user_ids:
            logger.info("Consistency Check: All users already have wallets. No migration needed.")
            return

        logger.critical(
            "Found %s users without wallets (user_ids=%s). No wallets were created; manual recovery is required.",
            len(user_ids),
            user_ids,
        )

if __name__ == "__main__":
    asyncio.run(ensure_all_users_have_wallets())