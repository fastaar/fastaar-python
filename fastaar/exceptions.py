class FastaarException(Exception):
    """
    Exception raised for errors in the Fastaar SDK.

    Attributes:
        message -- explanation of the error
        error_type -- stable API error code, e.g. "authentication_error",
                      "subscription_required", "transaction_limit_reached",
                      "connection_error", or "api_error"
        status_code -- HTTP status code returned by the API (0 if connection error)
    """

    def __init__(self, message: str, error_type: str = "api_error", status_code: int = 0):
        super().__init__(message)
        self.error_type = error_type
        self.status_code = status_code
