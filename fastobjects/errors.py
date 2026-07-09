"""Exceções da FastObjects — sempre com mensagens acionáveis."""


class CapacityError(Exception):
    """Levantada quando um spawn excede a capacidade do batch."""


class AtlasOverflowError(Exception):
    """Levantada quando as imagens não cabem num atlas do tamanho máximo."""
