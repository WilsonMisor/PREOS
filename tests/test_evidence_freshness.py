import unittest
class T(unittest.TestCase):
 def test_changed_binding_invalidates(self):
  old={'commit':'abc','config':'1'}; new={'commit':'def','config':'1'}; self.assertTrue(any(k in new and new[k]!=v for k,v in old.items()))
