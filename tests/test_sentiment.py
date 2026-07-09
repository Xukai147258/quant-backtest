from engine.sentiment import RollingSentimentAnalyzer,BULLISH_KEYWORDS
def test_init():a=RollingSentimentAnalyzer();assert a.window==20
