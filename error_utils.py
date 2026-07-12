class BenchmarkApiError(RuntimeError):
    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable = retryable


def response_error_message(response):
    if not isinstance(response, dict):
        return f"malformed response: expected object, got {type(response).__name__}"
    error = response.get("error")
    if not error:
        return None
    if isinstance(error, dict):
        return str(error.get("message", error))
    return str(error)


def response_error_code(response):
    if not isinstance(response, dict):
        return None
    error = response.get("error")
    if isinstance(error, dict):
        return error.get("code")
    return response.get("code")


def is_internal_server_error_response(response):
    message = response_error_message(response)
    if not message:
        return False

    code = response_error_code(response)
    try:
        if int(code) >= 500:
            return True
    except (TypeError, ValueError):
        pass

    return "internal server error" in str(message).lower()
