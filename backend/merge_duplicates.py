import asyncio
import logging
import sys
import os
from decimal import Decimal
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

# Add project root to sys.path to allow imports from backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import async_session
from backend.models import (
    User, Wallet, Agent, Transaction, Payment, Loan, 
    LoanApplication, CryptoWallet, CryptoTransaction, 
    AuditLog, Commission, DataOrder, AirtimeCashSale
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("merge_duplicates")

async def merge_users(db: AsyncSession, master: User, slave: User):
    """
    Merges all financial and activity records from a slave user into a master user.
    """
    logger.info(f"Merging user ID {slave.id} into master user ID {master.id} (MoMo: {master.momo_number})")

    # 1. Synchronize Profile Metadata
    if not master.email and slave.email:
        master.email = slave.email
    if not master.phone_number and slave.phone_number:
        master.phone_number = slave.phone_number
    if not master.full_name and slave.full_name:
        master.full_name = slave.full_name
    if not master.google_id and slave.google_id:
        master.google_id = slave.google_id
    db.add(master)

    # 2. Merge Wallets (Fiat)
    master_wallet_res = await db.execute(select(Wallet).filter(Wallet.user_id == master.id))
    master_wallet = master_wallet_res.scalars().first()
    
    slave_wallet_res = await db.execute(select(Wallet).filter(Wallet.user_id == slave.id))
    slave_wallet = slave_wallet_res.scalars().first()

    if slave_wallet:
        if not master_wallet:
            slave_wallet.user_id = master.id
            db.add(slave_wallet)
            master_wallet = slave_wallet
        else:
            master_wallet.balance += (slave_wallet.balance or Decimal("0.00"))
            master_wallet.escrow_balance += (slave_wallet.escrow_balance or Decimal("0.00"))
            master_wallet.loan_balance += (slave_wallet.loan_balance or Decimal("0.00"))
            master_wallet.investment_balance += (slave_wallet.investment_balance or Decimal("0.00"))
            db.add(master_wallet)
            
            # Re-link transactions to the master wallet before deleting the slave wallet
            await db.execute(update(Transaction).where(Transaction.wallet_id == slave_wallet.id).values(wallet_id=master_wallet.id))
            await db.delete(slave_wallet)
    
    await db.flush()

    # 3. Merge Agent Records
    master_agent_res = await db.execute(select(Agent).filter(Agent.user_id == master.id))
    master_agent = master_agent_res.scalars().first()

    slave_agent_res = await db.execute(select(Agent).filter(Agent.user_id == slave.id))
    slave_agent = slave_agent_res.scalars().first()

    if slave_agent:
        if not master_agent:
            slave_agent.user_id = master.id
            db.add(slave_agent)
            master_agent = slave_agent
        else:
            master_agent.float_balance += (slave_agent.float_balance or Decimal("0.00"))
            master_agent.commission_balance += (slave_agent.commission_balance or Decimal("0.00"))
            db.add(master_agent)
            
            # Re-link all agent-scoped entities
            await db.execute(update(Transaction).where(Transaction.agent_id == slave_agent.id).values(agent_id=master_agent.id))
            await db.execute(update(Loan).where(Loan.agent_id == slave_agent.id).values(agent_id=master_agent.id))
            await db.execute(update(LoanApplication).where(LoanApplication.agent_id == slave_agent.id).values(agent_id=master_agent.id))
            await db.execute(update(Commission).where(Commission.agent_id == slave_agent.id).values(agent_id=master_agent.id))
            await db.execute(update(DataOrder).where(DataOrder.agent_id == slave_agent.id).values(agent_id=master_agent.id))
            
            await db.delete(slave_agent)
    
    await db.flush()

    # 4. Merge Crypto Wallets
    slave_crypto_res = await db.execute(select(CryptoWallet).filter(CryptoWallet.user_id == slave.id))
    for s_cw in slave_crypto_res.scalars().all():
        m_cw_res = await db.execute(select(CryptoWallet).filter(CryptoWallet.user_id == master.id, CryptoWallet.coin_type == s_cw.coin_type))
        m_cw = m_cw_res.scalars().first()
        
        if not m_cw:
            s_cw.user_id = master.id
            db.add(s_cw)
        else:
            m_cw.balance += (s_cw.balance or 0.0)
            db.add(m_cw)
            await db.execute(update(CryptoTransaction).where(CryptoTransaction.crypto_wallet_id == s_cw.id).values(crypto_wallet_id=m_cw.id))
            await db.delete(s_cw)

    # 5. Global re-linking for user_id FKs
    models_to_migrate = [
        Transaction, Payment, Loan, LoanApplication, CryptoTransaction, 
        AuditLog, Commission, DataOrder, AirtimeCashSale
    ]
    for model in models_to_migrate:
        await db.execute(update(model).where(model.user_id == slave.id).values(user_id=master.id))

    # 6. Finalize: Delete slave user
    await db.delete(slave)

async def run_cleanup():
    async with async_session() as db:
        logger.info("Searching for duplicate MoMo numbers...")
        
        # Identify momo_numbers present in more than one record
        stmt = (
            select(User.momo_number)
            .filter(User.momo_number.is_not(None))
            .group_by(User.momo_number)
            .having(func.count(User.id) > 1)
        )
        res = await db.execute(stmt)
        duplicate_momo_numbers = res.scalars().all()

        if not duplicate_momo_numbers:
            logger.info("Cleanup complete: No duplicates found.")
            return

        logger.info(f"Found {len(duplicate_momo_numbers)} identities with duplicates.")

        for momo in duplicate_momo_numbers:
            # Prioritize the most 'official' account: Verified > Oldest
            users_res = await db.execute(
                select(User)
                .filter(User.momo_number == momo)
                .order_by(User.is_verified.desc(), User.created_at.asc())
            )
            users = users_res.scalars().all()
            
            master = users[0]
            slaves = users[1:]
            
            for slave in slaves:
                await merge_users(db, master, slave)
        
        await db.commit()
        logger.info("Success: Database cleanup and merging completed.")

if __name__ == "__main__":
    asyncio.run(run_cleanup())