class Classifier:
    def __init__(self, policy):
        self.policy = policy

    def classify(self, cookie, status=200):
        return self.policy.classify(cookie, status)
