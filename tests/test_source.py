from unittest.mock import Mock

import pytest

from bupt_rag.models import AppError
from bupt_rag.source import GitHubSource


@pytest.mark.parametrize(
    "body", [{"truncated": True, "tree": []}, {"tree": None}, {"tree": [{}]}, {"tree": []}]
)
def test_incomplete_remote_manifest_aborts(body):
    source = GitHubSource()
    source._get = Mock(return_value=Mock(json=Mock(return_value=body)))
    with pytest.raises(AppError):
        source.fetch("a" * 40)
    source.close()


def test_malformed_remote_json_is_service_error():
    source = GitHubSource()
    source._get = Mock(return_value=Mock(json=Mock(side_effect=ValueError("not JSON"))))
    with pytest.raises(AppError) as err:
        source.resolve("main")
    assert err.value.status == 503
    source.close()
