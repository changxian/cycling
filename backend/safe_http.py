import ipaddress
import socket

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.exceptions import NewConnectionError
from urllib3.util.connection import create_connection


def is_public_address(value):
    address = ipaddress.ip_address(value)
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return address.is_global


def connect_public(connection):
    try:
        addresses = socket.getaddrinfo(connection.host, connection.port, type=socket.SOCK_STREAM)
        if not addresses or any(not is_public_address(item[4][0]) for item in addresses):
            raise NewConnectionError(connection, "普通账号仅可连接公网AI服务。")
        last_error = None
        for address in addresses:
            try:
                return create_connection(
                    (address[4][0], connection.port), connection.timeout,
                    source_address=connection.source_address, socket_options=connection.socket_options,
                )
            except OSError as error:
                last_error = error
        raise NewConnectionError(connection, str(last_error))
    except (OSError, ValueError) as error:
        raise NewConnectionError(connection, "无法连接公网AI服务。") from error


class PublicHTTPConnection(HTTPConnection):
    def _new_conn(self):
        return connect_public(self)


class PublicHTTPSConnection(HTTPSConnection):
    def _new_conn(self):
        return connect_public(self)


class PublicHTTPPool(HTTPConnectionPool):
    ConnectionCls = PublicHTTPConnection


class PublicHTTPSPool(HTTPSConnectionPool):
    ConnectionCls = PublicHTTPSConnection


class PublicAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = {"http": PublicHTTPPool, "https": PublicHTTPSPool}


def post_public(url, **kwargs):
    with requests.Session() as session:
        session.trust_env = False
        session.mount("http://", PublicAdapter())
        session.mount("https://", PublicAdapter())
        kwargs["allow_redirects"] = False
        return session.post(url, **kwargs)
