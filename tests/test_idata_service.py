from __future__ import annotations

import pytest
import httpx

from backend.services.idata_service import IDataApiError, IDataService


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url",
    [
        "https://idatagh.com/wp-json/custom/v1",
        "https://idatagh.com/wp-json/custom/v1/place-order",
    ],
)
async def test_place_order_uses_documented_contract_and_endpoint(monkeypatch, base_url):
    captured = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "status": "success",
                "order_id": 1669242,
                "amount": 8.3,
                "network": "MTN",
                "beneficiary": "0547264035",
            }

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, url, *, json, headers):
            captured.update(url=url, json=json, headers=headers)
            return FakeResponse()

    monkeypatch.setattr("backend.services.idata_service.httpx.AsyncClient", FakeClient)
    service = IDataService()
    service.api_key = "provider-test-key"
    service.base_url = base_url

    response = await service.place_order(
        network="mtn",
        beneficiary="0547264035",
        bundle_package_id=2,
    )

    assert captured["url"] == "https://idatagh.com/wp-json/custom/v1/place-order"
    assert captured["json"] == {
        "network": "mtn",
        "beneficiary": "0547264035",
        "pa_data-bundle-packages": 2,
    }
    assert captured["headers"]["Authorization"] == "Bearer provider-test-key"
    assert response["order_id"] == 1669242
    assert IDataService.order_receipt({**response, "debug": "private provider detail"}) == {
        "status": "success",
        "order_id": 1669242,
        "amount": 8.3,
        "network": "MTN",
        "beneficiary": "0547264035",
    }


@pytest.mark.asyncio
async def test_place_order_does_not_expose_provider_error_body(monkeypatch):
    class FakeResponse:
        status_code = 401
        text = "secret provider diagnostic"

        @staticmethod
        def json():
            return {"message": "secret provider diagnostic"}

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr("backend.services.idata_service.httpx.AsyncClient", FakeClient)
    service = IDataService()
    service.api_key = "provider-test-key"
    service.base_url = "https://idatagh.com/wp-json/custom/v1"

    with pytest.raises(IDataApiError) as error:
        await service.place_order(network="mtn", beneficiary="0547264035", bundle_package_id=2)

    assert "secret provider diagnostic" not in str(error.value)
    assert error.value.response is None


@pytest.mark.asyncio
async def test_uncertain_provider_timeout_is_marked_for_status_check(monkeypatch):
    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, *_args, **_kwargs):
            raise httpx.ReadTimeout("private transport details")

    monkeypatch.setattr("backend.services.idata_service.httpx.AsyncClient", FakeClient)
    service = IDataService()
    service.api_key = "provider-test-key"
    service.base_url = "https://idatagh.com/wp-json/custom/v1"

    with pytest.raises(IDataApiError) as error:
        await service.place_order(network="mtn", beneficiary="0547264035", bundle_package_id=2)

    assert error.value.outcome_unknown is True
    assert "private transport details" not in str(error.value)
