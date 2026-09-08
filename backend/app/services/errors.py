"""Domain-level errors. Services raise these; controllers translate them
into HTTP responses. This keeps the service layer free of any web
framework dependency (Single Responsibility / testable in isolation)."""


class DomainError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class NotFoundError(DomainError):
    def __init__(self, message: str = "Not found") -> None:
        super().__init__(message, status_code=404)


class ConflictError(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=409)


class ValidationError(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=422)


class AuthError(DomainError):
    def __init__(self, message: str = "Not authenticated") -> None:
        super().__init__(message, status_code=401)


class ForbiddenError(DomainError):
    def __init__(self, message: str = "Not allowed") -> None:
        super().__init__(message, status_code=403)
