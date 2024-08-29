from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from api.models import Provider
from tasks.jobs.connection import check_provider_connection


@pytest.mark.parametrize(
    "provider_data, provider_class",
    [
        (
            {"provider": "aws", "provider_id": "123456789012", "alias": "aws"},
            "AwsProvider",
        ),
    ],
)
@pytest.mark.django_db
def test_check_provider_connection(get_tenant, provider_data, provider_class):
    provider = Provider.objects.create(**provider_data, tenant_id=get_tenant.id)

    mock_test_connection_result = MagicMock()
    mock_test_connection_result.is_connected = True

    with patch(
        f"tasks.jobs.connection.{provider_class}.test_connection"
    ) as mock_test_connection:
        mock_test_connection.return_value = mock_test_connection_result

        check_provider_connection(
            provider_id=str(provider.id),
        )
        provider.refresh_from_db()

        mock_test_connection.assert_called_once()
        assert provider.connected is True
        assert provider.connection_last_checked_at is not None
        assert provider.connection_last_checked_at <= datetime.now(tz=timezone.utc)


@patch("tasks.jobs.connection.Provider.objects.get")
@pytest.mark.django_db
def test_check_provider_connection_unsupported_provider(mock_provider_get):
    mock_provider_instance = MagicMock()
    mock_provider_instance.provider = "UNSUPPORTED_PROVIDER"
    mock_provider_get.return_value = mock_provider_instance

    with pytest.raises(
        ValueError, match="Provider type UNSUPPORTED_PROVIDER not supported"
    ):
        check_provider_connection("provider_id")


@patch("tasks.jobs.connection.Provider.objects.get")
@patch("tasks.jobs.connection.AwsProvider.test_connection")
@pytest.mark.django_db
def test_check_provider_connection_exception(mock_test_connection, mock_provider_get):
    mock_provider_instance = MagicMock()
    mock_provider_instance.provider = Provider.ProviderChoices.AWS.value
    mock_provider_get.return_value = mock_provider_instance

    mock_test_connection.return_value = MagicMock()
    mock_test_connection.return_value.is_connected = False
    mock_test_connection.return_value.error = Exception()

    result = check_provider_connection(provider_id="provider_id")

    assert result["connected"] is False
    assert result["error"] is not None

    mock_provider_instance.save.assert_called_once()
    assert mock_provider_instance.connected is False
