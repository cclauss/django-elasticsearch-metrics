"""elasticsearch_metrics.util.anon_enough: utilities for "anonymous enough" privacy-minded metrics"""

import base64
import collections
import datetime
import hashlib
import json

from django.utils import timezone


def opaque_key(
    key_parts: collections.abc.Iterable[object],
) -> str:
    """opaque_key: hash function for use in privacy-protecting metrics

    positional args: non-None, str-able things to hash

    >>> opaque_key(['hello'])
    >>> opaque_key(['hello', 'hello', 'hello'])
    """
    _plain_key = json.dumps([str(_part) for _part in key_parts])
    return base64.b85encode(
        hashlib.blake2b(bytes(_plain_key, encoding="utf")).digest()
    ).decode()


def opaque_sessionhour_id(
    *,
    client_session_id: str = "",
    user_id: str = "",
    request_host: str = "",
    request_useragent: str = "",
) -> str:
    """opaque_sessionhour_id:

    get a hashed id for a "user session" compatible with COUNTER code of practice:
    https://cop5.projectcounter.org/en/5.0.2/07-processing/03-counting-unique-items.html
    """
    _now = timezone.now().astimezone(datetime.UTC)
    _today_str = _now.date().isoformat()

    # "A user session is defined any of the following ways: ..." (quotes out of order)
    if client_session_id:
        # "...by a logged user cookie + transaction date + hour of day..."
        _session_id_parts = [client_session_id, _today_str, _now.hour]
    elif user_id:
        # "...by a logged user ID (if users log in with personal accounts)
        #  + transaction date + hour of day (day is divided into 24 one-hour slices) ..."
        _session_id_parts = [user_id, _today_str, _now.hour]
    elif request_host and request_useragent:
        # "...or by a combination of IP address + user agent + transaction date + hour of day."
        _session_id_parts = [request_host, request_useragent, _today_str, _now.hour]
    else:
        raise ValueError("not enough to make a session id")
    return opaque_key(_session_id_parts)


__test__ = {
    "opaque_sessionhour_id": """
>>> from unittest.mock import patch
>>> _now_patcher = patch('django.utils.timezone.now', return_value=datetime.datetime(1234, 5, 6, 7))
>>> _now_patcher.start() and None
>>> opaque_sessionhour_id(client_session_id='foo')
'962bc7704445a68df301da544869719b3d892a50fe74972b59b106c983dd7379'
>>> opaque_sessionhour_id(client_session_id='feh', user_id='blah')
'd16d70b136c623da4832057cc5493d15246d379d21d4536be204402e4155d29c'
>>> opaque_sessionhour_id(request_host='999.999.999.999', request_useragent='hehe')
'109cf42215e26373a8977dcb7439b2b32a9797cfc5d6d1c6e5168cbb8dde6acd'
>>> _now_patcher.stop() or None
""",
}
