class InvestmentCalculator:
    DAILY_RATE = 0.02

    @classmethod
    def calculate_daily(cls, amount):
        return float(amount) * cls.DAILY_RATE

    @classmethod
    def calculate_total(cls, amount, days):
        daily = cls.calculate_daily(amount)
        return daily * int(days)

