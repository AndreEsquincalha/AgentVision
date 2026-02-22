class NotFoundException(Exception):
    """Excecao para recurso nao encontrado (HTTP 404)."""

    def __init__(self, message: str = 'Recurso nao encontrado') -> None:
        self.message = message
        super().__init__(self.message)


class UnauthorizedException(Exception):
    """Excecao para acesso nao autorizado (HTTP 401)."""

    def __init__(self, message: str = 'Nao autorizado') -> None:
        self.message = message
        super().__init__(self.message)


class ForbiddenException(Exception):
    """Excecao para acesso proibido (HTTP 403)."""

    def __init__(self, message: str = 'Acesso proibido') -> None:
        self.message = message
        super().__init__(self.message)


class BadRequestException(Exception):
    """Excecao para requisicao invalida (HTTP 400)."""

    def __init__(self, message: str = 'Requisicao invalida') -> None:
        self.message = message
        super().__init__(self.message)
