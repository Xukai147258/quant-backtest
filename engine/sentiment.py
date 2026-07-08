"""sentiment stubs"""
import pandas as pd
import numpy as np
class RollingSentimentAnalyzer:
    def __init__(self, window=20):
        self.window = window
    def compute_index(self, news_data):
        raise NotImplementedError("Task_3.3")
