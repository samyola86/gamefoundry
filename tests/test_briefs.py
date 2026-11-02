import base64
import json
from pathlib import Path
import tempfile
import unittest
from briefs import BriefStore, OwnerRequired, RevisionConflict

PNG='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1kAAAAASUVORK5CYII='
PID='aabbccddeeff0011'

class BriefTests(unittest.TestCase):
    def test_only_owner_can_save_and_password_is_not_stored(self):
        with tempfile.TemporaryDirectory() as directory:
            store=BriefStore(directory)
            body={'revision':0,'fields':{'vision':'User direction'},'images':[]}
            with self.assertRaises(OwnerRequired):store.save(PID,body,'normal-dashboard-token')
            self.assertEqual(store.read(PID)['revision'],0)
            token=store.unlock('test-only-owner-passphrase',setup=True,confirm='test-only-owner-passphrase')
            self.assertNotIn('test-only-owner-passphrase',(Path(directory)/'owner.json').read_text())
            with self.assertRaises(OwnerRequired):store.unlock('wrong-password')
            saved=store.save(PID,body,token)
            self.assertEqual(saved['fields']['vision'],'User direction')
            self.assertEqual(saved['assistant_access'],'read-only')
            store.lock(token)
            with self.assertRaises(OwnerRequired):store.save(PID,{**body,'revision':1},token)

    def test_images_and_prior_revisions_survive_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            store=BriefStore(directory);token=store.unlock('synthetic-test-pass',setup=True,confirm='synthetic-test-pass')
            first=store.save(PID,{'revision':0,'fields':{'characters':'A character'},'images':[{'name':'reference.png','caption':'Hero','section':'characters','data':PNG}]},token)
            path,mime=store.image(PID,first['images'][0]['id'])
            self.assertEqual(path.read_bytes(),base64.b64decode(PNG));self.assertEqual(mime,'image/png')
            with self.assertRaises(RevisionConflict):store.save(PID,{'revision':0},token)
            store.save(PID,{'revision':1,'fields':{'characters':'Updated by owner'},'images':[]},token)
            history=json.loads((Path(directory)/PID/'history/1.json').read_text())
            self.assertEqual(history['fields']['characters'],'A character')
            self.assertTrue(path.exists())

    def test_non_images_and_path_traversal_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store=BriefStore(directory);token=store.unlock('synthetic-test-pass',setup=True,confirm='synthetic-test-pass')
            with self.assertRaises(ValueError):store.save(PID,{'revision':0,'images':[{'name':'fake.png','data':base64.b64encode(b'<script>bad</script>').decode()}]},token)
            with self.assertRaises(ValueError):store.image(PID,'../../owner.json')
            self.assertEqual(store.read(PID)['revision'],0)

    def test_reading_an_empty_brief_does_not_create_project_files(self):
        with tempfile.TemporaryDirectory() as directory:
            store=BriefStore(directory)
            self.assertEqual(store.read(PID)['owner'],'user')
            self.assertFalse((Path(directory)/PID).exists())

if __name__=='__main__':unittest.main()
