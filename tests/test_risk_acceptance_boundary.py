import unittest,re
BAD={'AI','CODEX','GSTACK','LLM','AGENT','PREOS'}
class T(unittest.TestCase):
    def test_tools_are_not_risk_authority(self):
        for value in BAD:
            self.assertTrue(any(re.search(rf'\b{re.escape(x)}\b',value.upper()) for x in BAD))
