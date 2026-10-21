from rest_framework.views import exception_handler


def standard_exception_handler(exc, context):
    """Wrap DRF errors in a consistent envelope.

    Every error response looks the same so the frontend can handle failures
    generically instead of parsing a different shape per endpoint (plan.md §6)::

        {"error": {"code": "not_found", "message": "...", "details": {...}}}
    """
    response = exception_handler(exc, context)
    if response is None:
        return None

    detail = response.data
    code = "error"
    message = "Something went wrong."

    if isinstance(detail, dict) and "detail" in detail:
        message = str(detail["detail"])
        code = getattr(detail["detail"], "code", None) or _code_for_status(response.status_code)
        details = {}
    elif isinstance(detail, dict):
        code = "validation_error"
        message = "The submitted data was invalid."
        details = detail
    else:
        details = {"errors": detail}

    response.data = {"error": {"code": code, "message": message, "details": details}}
    return response


def _code_for_status(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthenticated",
        403: "permission_denied",
        404: "not_found",
        405: "method_not_allowed",
        429: "throttled",
    }.get(status_code, "error")
