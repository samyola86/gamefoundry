import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import config

class CoreTests(unittest.TestCase):
    def test_discovery_does_not_invent_missing_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ,{'ProgramFiles':directory,'LOCALAPPDATA':directory}):
                with patch('config.shutil.which',return_value=None):
                    tools=config.discover_tools()
            self.assertEqual(tools['blender'],'')
            self.assertEqual(tools['vscode'],'')

    def test_project_registration_is_read_only_and_unique(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ,{'GAMEFOUNDRY_HOME':directory}):
                spec=importlib.util.spec_from_file_location('test_server',Path(__file__).resolve().parents[1]/'server.py')
                server=importlib.util.module_from_spec(spec);spec.loader.exec_module(server)
                project=Path(directory)/'Existing.uproject';project.write_text('{"FileVersion":3}')
                before=project.read_bytes()
                item=server.register_project({'uproject':str(project)})
                self.assertFalse(item['managed'])
                self.assertEqual(before,project.read_bytes())
                self.assertIsNone(server.ensure_blend(item))
                with self.assertRaises(ValueError):server.register_project({'uproject':str(project)})

    def test_invalid_game_names_cannot_escape_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ,{'GAMEFOUNDRY_HOME':directory}):
                spec=importlib.util.spec_from_file_location('names_server',Path(__file__).resolve().parents[1]/'server.py')
                server=importlib.util.module_from_spec(spec);spec.loader.exec_module(server)
                for name in ['../escape','CON','LPT1','A/B']:
                    with self.assertRaises(ValueError):server.create_project({'name':name,'folder':directory})

    def test_settings_reject_remote_model_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ,{'GAMEFOUNDRY_HOME':directory}):
                spec=importlib.util.spec_from_file_location('settings_server',Path(__file__).resolve().parents[1]/'server.py')
                server=importlib.util.module_from_spec(spec);spec.loader.exec_module(server)
                with patch.object(server,'executable',return_value='valid.exe'):
                    with self.assertRaises(ValueError):server.update_settings({'ollama_url':'https://example.com'})

if __name__=='__main__':unittest.main()
