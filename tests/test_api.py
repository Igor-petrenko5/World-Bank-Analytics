
from unittest.mock import Mock

import pytest

from src.api.client import WorldBankAPI


def test_pagination():
    api = WorldBankAPI()

    api.get_page = Mock(side_effect=[
        (
            {"page": 1, "pages": 2, "total": 2},
            [{"id": "USA"}]
        ),
        (
            {"page": 2, "pages": 2, "total": 2},
            [{"id": "RUS"}]
        )
    ])

    _, records = api.get_all("country")

    assert len(records) == 2
    assert api.get_page.call_count == 2


def test_incomplete_collection():
    api = WorldBankAPI()

    api.get_page = Mock(return_value=(
        {"page": 1, "pages": 1, "total": 10},
        [{"id": "USA"}]
    ))

    with pytest.raises(ValueError):
        api.get_all("country")


def test_wrong_page():
    api = WorldBankAPI()

    api.get_page = Mock(return_value=(
        {"page": 5, "pages": 5, "total": 1},
        [{"id": "USA"}]
    ))

    with pytest.raises(ValueError):
        api.get_all("country")


def test_invalid_response():
    api = WorldBankAPI()

    response = Mock()
    response.url = "https://api.worldbank.org/v2/country"
    response.json.return_value = {
        "error": "Invalid response"
    }

    api.session.get = Mock(return_value=response)

    with pytest.raises(ValueError):
        api.get_page("country")
