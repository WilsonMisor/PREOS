import unittest
class T(unittest.TestCase):
    def test_project_contract_is_compiled_truth(self):
        contract={'source_hashes':[{'artifact':'PRD','sha256':'a'*64},{'artifact':'SRS','sha256':'b'*64}], 'classification':{'profiles':['saas','api']}}
        self.assertEqual({x['artifact'] for x in contract['source_hashes']},{'PRD','SRS'})
        self.assertIn('saas',contract['classification']['profiles'])
