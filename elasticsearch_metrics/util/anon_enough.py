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
    'V0`d<8NsX5UQjv_YK_fD+9!nr;^?`WvJ%~vB<}v4=Gsk7VRO#CB5!jR?223lNbvbOIvX_7sNpXimPncE'
    >>> opaque_key(['hello', 'hello', 'hello'])
    '*58u_=`?3#G!N(%j!3kqU7#Npt>Xvj=|3<75BRoi$0j;F-*3V+Cc?P1FvcVW76T_`5^NaI*_3787SsBn'
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
    _now = timezone.now().astimezone(datetime.timezone.utc)
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
'R26L*vmd?|G}S5AZ}ONXq>^B*T-!TLCE`uboEXF-LpK8Hysi$nUve^2aG~PTWiX<6BDv}wQtowotKSdV'
>>> opaque_sessionhour_id(client_session_id='feh', user_id='blah')
'JfeGFBfil1y$8fnmhi)8LU4}9vUBX6VfHmDPiVfiB~0nT&%3tKWsTTF_z2wynPj}`EF=}Y6=?}e5nDK0'
>>> opaque_sessionhour_id(request_host='999.999.999.999', request_useragent='hehe')
'Q^-x^v~@WQRHrWsbbji+pNmz)1`sp3SywCJ4n`W_aoY0tfbL6byxqUpw#DXoqU3>DtZC*^D@qjc7EmO='
>>> _now_patcher.stop() or None
""",
}
