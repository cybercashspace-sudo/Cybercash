class NetworkDetector:
    prefixes = {
        "024": "MTN",
        "025": "MTN",
        "053": "MTN",
        "054": "MTN",
        "055": "MTN",
        "059": "MTN",
        "020": "Telecel",
        "050": "Telecel",
        "026": "AirtelTigo",
        "027": "AirtelTigo",
        "056": "AirtelTigo",
        "057": "AirtelTigo",
    }

    @classmethod
    def detect(cls, phone):
        prefix = str(phone or "")[:3]
        return cls.prefixes.get(prefix, "Unknown")

