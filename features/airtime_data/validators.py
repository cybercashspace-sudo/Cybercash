from core.validation import (
    detect_ghana_network,
    normalize_phone,
    validate_amount as core_validate_amount,
    validate_network as core_validate_network,
)


SUPPORTED_NETWORKS = {"mtn", "telecel", "airteltigo"}


def validate_amount(value):
    return core_validate_amount(
        value,
        label="amount",
        invalid_message="Enter a valid amount.",
        minimum_message="Enter an amount greater than zero.",
    )


def validate_network(network):
    return core_validate_network(network, SUPPORTED_NETWORKS, label="mobile network")


def detect_network(phone):
    return detect_ghana_network(phone)
