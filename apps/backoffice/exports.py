"""Streamed CSV downloads for the back-office.

Vercel caps a response at 4.5 MB, so an export must stream rather than buffer: ``csv.writer``
writes into a pseudo-buffer that returns each rendered line, and ``StreamingHttpResponse`` sends
them as they are produced. Callers pass a header and a row iterator built off a ``.iterator()``
queryset, so memory stays flat no matter how many rows the filter matches.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Iterator

from django.http import StreamingHttpResponse


class _Echo:
    """A file-like object whose ``write`` just returns the line, for ``csv.writer`` to yield."""

    def write(self, value: str) -> str:
        return value


def stream_csv(filename: str, header: Iterable, rows: Iterable[Iterable]) -> StreamingHttpResponse:
    writer = csv.writer(_Echo())

    def generate() -> Iterator[str]:
        yield writer.writerow(header)
        for row in rows:
            yield writer.writerow(row)

    response = StreamingHttpResponse(generate(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
