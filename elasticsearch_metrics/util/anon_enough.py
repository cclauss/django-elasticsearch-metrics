"""elasticsearch_metrics.util.anon_enough: utilities for "anonymous enough" privacy-minded metrics"""

import collections
import datetime
import hashlib
import json


def opaque_key(key_parts: collections.abc.Iterable[str]) -> str:
    """opaque_key: hash function for use in privacy-protecting metrics

    positional args: non-None, str-able things to hash

    >>> opaque_key(['hello'])
    'c7a0f7154e64cd96c617f251dc12c4396b7234c2856ccf4860ab7af537dfcdd9'
    >>> opaque_key(['hello', 'hello', 'hello'])
    'ebb92fdbff663124680971757e5d70a3e90a5708d48503962a16a30cde801aea'
    """
    # plain_key = '|'.join(map(str, key_parts))
    _plain_key = json.dumps([str(_part) for _part in key_parts])
    return hashlib.sha256(bytes(_plain_key, encoding="utf")).hexdigest()


def opaque_session_id(
    *,
    client_session_id: str = "",
    user_id: str = "",
    request_host: str = "",
    request_useragent: str = "",
) -> str:
    """opaque_session_id:

    get a "user session" as described in the COUNTER code of practice:
    https://cop5.projectcounter.org/en/5.0.2/07-processing/03-counting-unique-items.html
    """
    _now = datetime.datetime.now(datetime.UTC)
    _today_str = _now.date().isoformat()

    # "A user session is defined any of the following ways: ..."
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
