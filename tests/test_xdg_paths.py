"""Snapshots and theme adapters must agree when XDG directories live outside HOME."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from sumi import profiles
from sumi.paths import config_path, data_root

class XdgPathsTests(unittest.TestCase):
    def test_snapshot_restore_outside_home_and_spaces(self):
        with tempfile.TemporaryDirectory(prefix='sumi paths ') as tmp:
            root=Path(tmp); home=root/'home'; home.mkdir()
            config=root/'custom config'; data=root/'custom data'
            with patch.dict(os.environ, {'XDG_CONFIG_HOME':str(config),'XDG_DATA_HOME':str(data),'XDG_STATE_HOME':str(root/'state')}):
                target=config/'hypr/test.lua'; target.parent.mkdir(parents=True); target.write_text('before')
                snapshot=root/'backup'
                profiles.capture_snapshot(home,snapshot,paths=('.config/hypr/test.lua',))
                target.write_text('after')
                profiles.restore_snapshot(snapshot,home)
                self.assertEqual(target.read_text(),'before')
                self.assertFalse((home/'.config').exists())
                self.assertEqual(profiles.state_path(home),root/'state/sumi')
                self.assertEqual(profiles.data_path(home),data/'sumi')
                with patch.dict(os.environ, {'XDG_CONFIG_HOME':str(root/'changed')}):
                    with self.assertRaises(profiles.ProfileError): profiles.restore_snapshot(snapshot,home)

if __name__=='__main__': unittest.main()
