# -*- coding: utf-8 -*-
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
START_DEV = ROOT / 'start-dev.bat'


@unittest.skipUnless(os.name == 'nt', 'start-dev.bat is Windows-only')
class DevLauncherTests(unittest.TestCase):
    def run_with_listener(self, local_endpoint):
        with tempfile.TemporaryDirectory() as directory:
            fake_netstat = Path(directory) / 'netstat.cmd'
            fake_netstat.write_text(
                '@echo off\r\n'
                f'echo   TCP    {local_endpoint}    0.0.0.0:0    LISTENING    4242\r\n',
                encoding='utf-8',
            )
            env = os.environ.copy()
            env['PATH'] = directory + os.pathsep + env.get('PATH', '')
            return subprocess.run(
                ['cmd.exe', '/d', '/c', str(START_DEV)],
                cwd=ROOT,
                env=env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

    def test_blocks_any_address_listening_on_development_port(self):
        for endpoint in ('127.0.0.1:7862', '0.0.0.0:7862', '[::]:7862'):
            with self.subTest(endpoint=endpoint):
                result = self.run_with_listener(endpoint)
                self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
                self.assertIn('Development web port 7862 is already in use', result.stdout)

    def test_does_not_confuse_port_suffix_with_development_port(self):
        result = self.run_with_listener('0.0.0.0:17862')
        self.assertNotEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertNotIn('Development web port 7862 is already in use', result.stdout)


if __name__ == '__main__':
    unittest.main()
