from core.validation import detect_ghana_network


class NetworkDetector:
    @classmethod
    def detect(cls, phone):
        network = detect_ghana_network(phone)
        if network == "mtn":
            return "MTN"
        if network == "telecel":
            return "Telecel"
        if network == "airteltigo":
            return "AirtelTigo"
        return "Unknown"
