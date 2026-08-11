from __future__ import annotations


class CyberCashError(Exception):
    """Base exception for app-specific failures."""


class AuthenticationError(CyberCashError):
    pass


class NetworkError(CyberCashError):
    pass


class ValidationError(CyberCashError):
    pass


class PaymentError(CyberCashError):
    pass


class InsufficientFundsError(CyberCashError):
    pass


class ServerError(CyberCashError):
    pass

