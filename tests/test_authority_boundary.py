import unittest,re
BAD={'AI','CODEX','GSTACK','LLM','AGENT'}
class T(unittest.TestCase):
 def test_ai_not_authority(self):
  a='Codex'; self.assertTrue(any(re.search(rf'\b{x}\b',a.upper()) for x in BAD))
