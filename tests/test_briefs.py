import base64
import json
from pathlib import Path
import tempfile
import unittest
from briefs import BriefStore, OwnerRequired, RevisionConflict

PNG='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1kAAAAASUVORK5CYII='
PID='aabbccddeeff0011'

class BriefTests(unittest.TestCase):
    def test_pdf_core_reference_is_owner_protected_and_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            store=BriefStore(directory);token=store.unlock('synthetic-pdf-pass',setup=True,confirm='synthetic-pdf-pass')
            pdf=b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n'
            body={'revision':0,'fields':{'look_feel':'Explicit user style'},'documents':[{'name':'design.pdf','caption':'Core game design','section':'all','data':base64.b64encode(pdf).decode()}]}
            with self.assertRaises(OwnerRequired):store.save(PID,body,None)
            first=store.save(PID,body,token)
            ref=first['documents'][0]
            self.assertEqual(ref['role'],'core_reference')
            self.assertEqual(store.document(PID,ref['id']).read_bytes(),pdf)
            self.assertIn('missing descriptions',first['reference_policy'])
            second=store.save(PID,{'revision':1,'fields':first['fields'],'images':[]},token)
            self.assertEqual(second['documents'][0]['id'],ref['id'])
            self.assertEqual(second['fields']['look_feel'],'Explicit user style')
            store.save(PID,{'revision':2,'fields':second['fields'],'documents':[]},token)
            self.assertTrue(store.document(PID,ref['id']).exists())
            history=json.loads((Path(directory)/PID/'history/2.json').read_text())
            self.assertEqual(history['documents'][0]['id'],ref['id'])
            with self.assertRaises(ValueError):store.document(PID,'../../owner.json')

    def test_master_storyboard_tags_order_and_compatibility(self):
        with tempfile.TemporaryDirectory() as directory:
            store=BriefStore(directory);token=store.unlock('synthetic-test-pass',setup=True,confirm='synthetic-test-pass')
            refs=[{'name':name,'data':PNG,'role':'master_reference','tags':['Design style','Character design style']} for name in ['Frame one','Frame two']]
            with self.assertRaises(OwnerRequired):store.save(PID,{'revision':0,'images':refs},None)
            first=store.save(PID,{'revision':0,'images':refs},token)
            self.assertEqual(first['images'][0]['role'],'master_reference')
            self.assertEqual(first['images'][0]['tags'],refs[0]['tags'])
            second=store.save(PID,{'revision':1,'images':list(reversed(first['images']))},token)
            self.assertEqual([r['name'] for r in second['images']],['Frame two','Frame one'])
            third=store.save(PID,{'revision':2,'fields':second['fields']},token)
            self.assertEqual(third['images'],second['images'])
            for bad in ['not-a-list',['x'*61],['tag']*13]:
                with self.assertRaises(ValueError):store.save(PID,{'revision':3,'images':[{**third['images'][0],'tags':bad}]},token)
            self.assertEqual(store.read(PID)['revision'],3)

    def test_invalid_pdf_does_not_change_saved_brief(self):
        with tempfile.TemporaryDirectory() as directory:
            store=BriefStore(directory);token=store.unlock('synthetic-pdf-pass',setup=True,confirm='synthetic-pdf-pass')
            for bad in [b'<html>not a pdf</html>',b'%PDF-1.4\ntruncated']:
                with self.assertRaises(ValueError):store.save(PID,{'revision':0,'documents':[{'name':'fake.pdf','data':base64.b64encode(bad).decode()}]},token)
                self.assertEqual(store.read(PID)['revision'],0)

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
