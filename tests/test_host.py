"""Host-side checks for provisioning and asset integrity; no physical board needed."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from configure import make_settings, write_private
from prepare import verified_download
from project import serial_port


class ProvisioningTests(unittest.TestCase):
    def test_credentials_match_board_hash_and_are_unique(self):
        one, access = make_settings('Example 2.4G','sample-password','ESP32-LLM','192.168.4.1')
        two, _ = make_settings('Example 2.4G','sample-password','ESP32-LLM','192.168.4.1')
        self.assertEqual(hashlib.sha256((one['salt']+access['password']).encode()).hexdigest(),one['password_hash'])
        self.assertEqual(one['api_key'],access['api_key'])
        self.assertNotEqual(one['api_key'],two['api_key'])
        self.assertNotIn('password',one)

    def test_invalid_wifi_inputs_rejected(self):
        for ssid,password in [('', 'long-password'),('中'*11,'long-password'),('wifi','short')]:
            with self.assertRaises(ValueError):
                make_settings(ssid,password,'ESP32-LLM','192.168.4.1')

    def test_private_file_does_not_overwrite_existing_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'settings.json'
            write_private(path,{'key':'original'})
            with self.assertRaises(FileExistsError):
                write_private(path,{'key':'replacement'})
            self.assertEqual(json.loads(path.read_text())['key'],'original')
            self.assertEqual(path.stat().st_mode & 0o777,0o600)

    def test_invalid_download_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'source.bin'; source.write_bytes(b'bad download')
            destination=Path(directory)/'model.bin'; destination.write_bytes(b'existing')
            with self.assertRaises(RuntimeError):
                verified_download(source.as_uri(),destination,hashlib.sha256(b'correct').hexdigest())
            self.assertEqual(destination.read_bytes(),b'existing')
            self.assertFalse(destination.with_suffix('.bin.part').exists())

    def test_offline_verification_checks_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'model.bin'; path.write_bytes(b'correct')
            verified_download('https://unused.invalid',path,hashlib.sha256(b'correct').hexdigest(),offline=True)
            with self.assertRaises(RuntimeError):
                verified_download('https://unused.invalid',path,'0'*64,offline=True)

    def test_serial_autodetect_refuses_ambiguity(self):
        from types import SimpleNamespace
        with patch('serial.tools.list_ports.comports',return_value=[
            SimpleNamespace(device='/dev/cu.usbmodem1',vid=0x303A),
            SimpleNamespace(device='/dev/cu.usbmodem2',vid=0x303A)]):
            with self.assertRaises(SystemExit):
                serial_port()
        self.assertEqual(serial_port('/dev/ttyUSB0'),'/dev/ttyUSB0')


if __name__ == '__main__':
    unittest.main()
