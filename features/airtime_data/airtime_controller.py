from features.airtime_data.airtime_service import AirtimeService
from features.airtime_data.network_detector import NetworkDetector
from features.airtime_data.validators import normalize_phone, validate_amount, validate_network


class AirtimeController:
    def __init__(self):
        self.service = AirtimeService()

    def prepare_purchase(self, phone, amount, network=""):
        normalized_phone = normalize_phone(phone)
        validated_amount = validate_amount(amount)
        detected_network = NetworkDetector.detect(normalized_phone)
        final_network = (network or "").strip() or detected_network
        validate_network(final_network)
        return {
            "phone": normalized_phone,
            "amount": validated_amount,
            "network": final_network,
        }

    def purchase(self, phone, amount, network=""):
        payload = self.prepare_purchase(phone, amount, network)
        return self.service.purchase(payload)

    def history(self, page=1, limit=20):
        payload = self.service.history(page=page, limit=limit)
        return payload

