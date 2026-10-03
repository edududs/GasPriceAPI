class DomainError(ValueError):
    """A value the domain cannot accept. The message is meant for the person who sent it."""


class UnknownStateError(DomainError):
    pass


class UnknownFuelError(DomainError):
    pass


class InvalidPriceError(DomainError):
    pass
