class CostExceedsLimit(Exception):
    def __init__(self, cost: int, limit: int) -> None:
        super().__init__(f"cost {cost} exceeds the client's limit of {limit}")
        self.cost = cost
        self.limit = limit