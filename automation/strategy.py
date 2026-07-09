from automation.task_queue import Task


class StrategyManager:
    def check_diversity(self, strategies):
        if len(strategies) < 2:
            return False
        names = [s.get("name", "") for s in strategies]
        unique_names = set(names)
        return len(unique_names) >= 2

    def select_best(self, strategies, task=None):
        if not strategies:
            return None
        return strategies[0]

    def calculate_budget(self, estimated_calls, remaining_quota):
        max_allowed = remaining_quota * 0.4
        if estimated_calls > max_allowed:
            return {
                "allowed": False,
                "max_allowed": max_allowed,
                "reason": f"estimated {estimated_calls} exceeds budget {max_allowed:.0f}",
            }
        return {"allowed": True, "max_allowed": max_allowed}
