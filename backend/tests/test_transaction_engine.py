import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.services.transaction_engine import TransactionEngine

@pytest.mark.asyncio
async def test_get_wallet_missing_raises_value_error():
    """
    Verify that _get_wallet raises ValueError when user wallet is missing,
    matching the stricter one-user-one-wallet invariant.
    """
    mock_db = AsyncMock()
    mock_ledger = MagicMock()
    engine = TransactionEngine(mock_db, mock_ledger)

    # Mock the DB result to return no wallet record
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_db.execute.return_value = mock_result

    user_id = 999
    with pytest.raises(ValueError) as excinfo:
        await engine._get_wallet(user_id)
    
    assert f"Wallet not found for user {user_id}" in str(excinfo.value)
    assert "Data integrity issue" in str(excinfo.value)

@pytest.mark.asyncio
async def test_get_wallet_success():
    """Verify that _get_wallet successfully returns the wallet object when found."""
    mock_db = AsyncMock()
    mock_ledger = MagicMock()
    engine = TransactionEngine(mock_db, mock_ledger)

    mock_wallet = MagicMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_wallet
    mock_db.execute.return_value = mock_result

    result = await engine._get_wallet(123)
    assert result == mock_wallet