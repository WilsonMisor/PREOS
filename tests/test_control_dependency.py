import unittest
ORDER={'GREEN':0,'AMBER':1,'UNKNOWN':2,'HUMAN REVIEW':3,'RED':4}
class T(unittest.TestCase):
    def test_unknown_prerequisite_contaminates_green(self):
        self.assertEqual(max(['GREEN','UNKNOWN'], key=ORDER.get),'UNKNOWN')
    def test_red_prerequisite_blocks(self):
        self.assertEqual(max(['GREEN','RED'], key=ORDER.get),'RED')
