"""API routes package."""


class ApiError(Exception):
    """An error that is returned to the client as a consistent JSON response.

    Response body: ``{"error": {"code": ..., "message": ..., "details": ...}}``
    (``details`` only when given).
    """

    def __init__(self, status_code: int, code: str, message: str, details=None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def error_payload(code: str, message: str, details=None) -> dict:
    """Build the standard error body."""
    error = {"code": code, "message": message}
    if details:
        error["details"] = details
    return {"error": error}


# Imported after ApiError exists because analysis_routes imports it from here.
from .analysis_routes import analysis_bp  # noqa: E402

__all__ = ["ApiError", "analysis_bp", "error_payload"]
