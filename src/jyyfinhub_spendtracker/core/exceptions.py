"""Base domain exception hierarchy. Concrete errors live in each feature's exceptions.py.

No framework imports: the API, web routes, and CLI all catch these same types. Services must never
raise HTTPException, or the CLI would depend on Starlette. `status_code` is here for the HTTP
handler to read and is simply ignored by the CLI.
"""


class SpendTrackerError(Exception):
    """Base for every domain error."""

    error_code = "internal_error"
    status_code = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(SpendTrackerError):
    """A requested record does not exist."""

    error_code = "not_found"
    status_code = 404


class ConflictError(SpendTrackerError):
    """The request clashes with existing data."""

    error_code = "conflict"
    status_code = 409


class ValidationError(SpendTrackerError):
    """The request is well formed but breaks a business rule."""

    error_code = "validation_error"
    status_code = 422
