"""What the suggest endpoint accepts.

Output is built by ``services.suggest`` as plain data rather than serialized from a model: a
suggestion is a handful of formatted strings, and the money in it is already formatted by the
one place that maps a product for display.
"""

from rest_framework import serializers

from .models import MAX_QUERY_LENGTH


class SuggestQuerySerializer(serializers.Serializer):
    """The only thing a caller sends. Capped here as well as in the service, because a 4 KB
    query string should be rejected before it reaches a tokeniser."""

    q = serializers.CharField(max_length=MAX_QUERY_LENGTH, allow_blank=True, required=False)
