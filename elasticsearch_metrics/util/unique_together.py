import collections

from elasticsearch_metrics.util.anon_enough import opaque_key


def get_unique_id(unique_together_field_values: collections.abc.Iterable[str]) -> str:
    # Set the document id to a hash of "unique together" fields
    # for "ON CONFLICT UPDATE" behavior -- if the document
    # already exists, it will be updated rather than duplicated.
    # Cannot detect/avoid conflicts this way, but that's ok.
    _key_values = []
    for _field_value in unique_together_field_values:
        if not isinstance(_field_value, str):
            raise ValueError(f"expected str, got {_field_value!r}")
        _key_values.append(_field_value)
    return opaque_key(_key_values)
