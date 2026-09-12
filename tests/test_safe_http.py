import socket
from unittest.mock import Mock

import pytest
import requests
from urllib3.exceptions import NewConnectionError

from backend.safe_http import PublicHTTPConnection, PublicHTTPSConnection, post_public


@pytest.mark.parametrize("connection_type", [PublicHTTPConnection, PublicHTTPSConnection])
@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.2", "169.254.169.254", "::1", "::ffff:127.0.0.1"])
def test_connection_rejects_private_dns_results(monkeypatch, connection_type, address):
    monkeypatch.setattr("backend.safe_http.socket.getaddrinfo", lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 80))])
    connect = Mock()
    monkeypatch.setattr("backend.safe_http.create_connection", connect)
    with pytest.raises(NewConnectionError):
        connection_type("ai.example")._new_conn()
    connect.assert_not_called()


@pytest.mark.parametrize("connection_type", [PublicHTTPConnection, PublicHTTPSConnection])
def test_connection_pins_validated_public_address(monkeypatch, connection_type):
    monkeypatch.setattr("backend.safe_http.socket.getaddrinfo", lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))])
    connect = Mock()
    monkeypatch.setattr("backend.safe_http.create_connection", connect)
    connection = connection_type("ai.example", port=443)
    assert connection._new_conn() == connect.return_value
    assert connect.call_args.args[0] == ("8.8.8.8", 443)
    assert connection.host == "ai.example"


@pytest.mark.parametrize("scheme", ["http", "https"])
def test_request_adapter_blocks_private_resolution_and_ignores_proxy(monkeypatch, scheme):
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:8080")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:8080")
    monkeypatch.setattr("backend.safe_http.socket.getaddrinfo", lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))])
    connect = Mock()
    monkeypatch.setattr("backend.safe_http.create_connection", connect)
    with pytest.raises(requests.ConnectionError):
        post_public(scheme + "://ai.example/v1", timeout=1)
    connect.assert_not_called()
