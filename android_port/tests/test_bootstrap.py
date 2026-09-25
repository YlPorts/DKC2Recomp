"""Synthetic bootstrap contracts, not gameplay or installation acceptance."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1]/'bootstrap.py'
spec = importlib.util.spec_from_file_location('bootstrap', MODULE)
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)

class BootstrapTests(unittest.TestCase):
    def test_git_blob_hash(self):
        data = b'hello\n'
        self.assertEqual(b.git_blob(data), hashlib.sha1(b'blob 6\0hello\n').hexdigest())

    def test_replace_once(self):
        self.assertEqual(b.once('abc', 'b', 'd'), 'adc')
        for text in ('abc', 'xx'):
            with self.assertRaises(ValueError): b.once(text, 'x', 'y')

    def test_section_boundaries(self):
        self.assertEqual(b.between('a<start>old<end>z', '<start>', '<end>', 'new'), 'anew<end>z')
        with self.assertRaises(ValueError): b.between('<end><start>', '<start>', '<end>', '')
        with self.assertRaises(ValueError): b.between('<start><start><end>', '<start>', '<end>', '')

    def test_revision_retargeting(self):
        text = 'DKC1 Dkc1 dkc1 '+b.OLD_ROM+' '+b.OLD_BASE+' '+b.OLD_ENGINE
        new = b.rename_game(text)
        for expected in ('DKC2', 'Dkc2', 'dkc2', b.ROM_SHA256, b.DKC2, b.ENGINE):
            self.assertIn(expected, new)
        for old in ('DKC1', 'Dkc1', 'dkc1', b.OLD_ROM, b.OLD_ENGINE):
            self.assertNotIn(old, new)

    def test_only_supported_display_modes(self):
        original = 'package com.ylports.dkc1recomp; ASPECTS={"4:3","16:10","16:9","21:9"}; get("aspect",0,0,3)'
        rendered = b.adapt_settings(original)
        self.assertIn('ASPECTS={"4:3","16:9"}', rendered)
        self.assertIn('ASPECTS.length-1', rendered)
        self.assertNotIn('21:9', rendered)

    def test_wrong_rom_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'bad.sfc'; path.write_bytes(b'not a rom')
            with self.assertRaises(ValueError): b.verify_rom(path)

    def test_wrong_rom_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'synthetic.sfc'; path.write_bytes(bytes(b.ROM_SIZE))
            with self.assertRaises(ValueError): b.verify_rom(path)

    def test_copier_header_normalization_synthetic_hash_only(self):
        # Mock only the expected digest in this unit test. Production never permits overrides.
        payload = bytes(b.ROM_SIZE)
        with tempfile.TemporaryDirectory() as tmp, patch.object(b, 'ROM_SHA256', hashlib.sha256(payload).hexdigest()):
            path = Path(tmp)/'synthetic.smc'; path.write_bytes(bytes(512)+payload)
            self.assertEqual(b.verify_rom(path), b.ROM_SHA256)
            path.write_bytes(bytes(1024)+payload)
            with self.assertRaises(ValueError): b.verify_rom(path)

    def test_checkout_refuses_existing_destination(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(b, 'run') as command:
            with self.assertRaises(FileExistsError): b.checkout('unused', b.DKC2, Path(tmp))
            command.assert_not_called()

    def test_native_guard_and_check_target(self):
        text = (MODULE.parent/'CMakeLists.txt').read_text()
        self.assertIn('Missing verified generated DKC2 game sources', text)
        self.assertIn('add_library(android_host_check OBJECT', text)
        self.assertIn('add_library(main SHARED ${ENGINE} ${GEN_C}', text)
        self.assertNotIn('dkc1_game.c', text)
        self.assertNotIn('stub', text.lower())

if __name__ == '__main__': unittest.main()
