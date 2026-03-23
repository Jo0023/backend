import pytest
from httpx import AsyncClient
from src.main import app


@pytest.mark.asyncio
async def test_submit_commission():

    async with AsyncClient(app=app, base_url="http://test") as client:

        payload = {
            "session_id": 1,
            "commissioner_id": 1,
            "project_type": "technical",
            "scores": {
                "1": 5,
                "2": 4,
                "3": 5,
                "4": 3,
                "5": 4
            },
            "comment": "Тест"
        }

        response = await client.post(
            "/v1/evaluation/commission/submit",
            json=payload
        )

        assert response.status_code in [200, 201]

