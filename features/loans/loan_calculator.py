class LoanCalculator:
    @staticmethod
    def remaining(principal, paid):
        return max(float(principal) - float(paid), 0)

