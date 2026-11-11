import unittest
from sumi.bluetooth_agent import ADDRESS, validate_reply

class PairingValidationTests(unittest.TestCase):
    def test_address_is_exact(self):
        self.assertTrue(ADDRESS.fullmatch('AA:bb:00:11:22:33'))
        for value in ('AA:BB', '/org/bluez/hci0', 'AA:bb:00:11:22:33\n'):
            self.assertIsNone(ADDRESS.fullmatch(value))

    def test_passkey_preserves_zero_and_range(self):
        self.assertEqual(validate_reply('RequestPasskey', '000001'), ('(u)', (1,)))
        self.assertEqual(validate_reply('RequestPasskey', '999999'), ('(u)', (999999,)))
        for value in ('1000000', '-1', '1e2', '１２', True):
            with self.assertRaises(ValueError): validate_reply('RequestPasskey', value)

    def test_pin_and_authorization(self):
        self.assertEqual(validate_reply('RequestPinCode', 'AB12'), ('(s)', ('AB12',)))
        self.assertEqual(validate_reply('RequestConfirmation', True), ('()', ()))
        for value in ('', 'a' * 17, 'hello world', '<script>'):
            with self.assertRaises(ValueError): validate_reply('RequestPinCode', value)
        with self.assertRaises(ValueError): validate_reply('RequestAuthorization', False)
