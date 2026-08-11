from features.airtime_data.data_service import DataService
from features.airtime_data.network_detector import NetworkDetector
from features.airtime_data.validators import normalize_phone, validate_amount, validate_network
from features.airtime_data.models import DataPackage


class DataController:
    def __init__(self):
        self.service = DataService()

    @staticmethod
    def _items(payload):
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("items", "results", "packages", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value
        return []

    def load_packages(self, network):
        network_text = (network or "").strip()
        validate_network(network_text)
        payload = self.service.packages(network_text.lower())
        return [DataPackage.from_dict(item).__dict__ for item in self._items(payload)]

    def prepare_purchase(self, phone, package, network=""):
        normalized_phone = normalize_phone(phone)
        final_network = (network or "").strip() or NetworkDetector.detect(normalized_phone)
        validate_network(final_network)
        if not package:
            raise ValueError("Select a data package.")
        if isinstance(package, dict):
            package_id = package.get("package_id") or package.get("id") or package.get("code")
            amount = package.get("price") or package.get("amount")
        else:
            package_id = str(package)
            amount = None
        return {
            "phone": normalized_phone,
            "network": final_network,
            "package_id": package_id,
            "amount": amount,
        }

    def purchase(self, phone, package, network=""):
        payload = self.prepare_purchase(phone, package, network)
        return self.service.purchase(payload)

    def history(self, page=1, limit=20):
        return self.service.history(page=page, limit=limit)

