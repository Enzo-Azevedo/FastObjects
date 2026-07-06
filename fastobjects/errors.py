"""Exceções da FastObjects — sempre com mensagens acionáveis."""


class CapacityError(Exception):
    """Levantada quando um spawn excede a capacidade do batch."""
