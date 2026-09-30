import base64
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from check_supabase_credentials import findings

def token(role):
    enc = lambda value: base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip('=')
    return enc({'alg': 'HS256'}) + '.' + enc({'role': role}) + '.syntheticSignature'

class CredentialTests(unittest.TestCase):
    def test_detection_and_safe_examples(self):
        cases = [
            (token('service_role'), True), (token('anon'), False),
            ('sb_' + 'secret_' + 'x' * 24, True),
            ('SUPABASE_JWT_SECRET=synthetic-test-value', True),
            ('SUPABASE_JWT_SECRET=\nOTHER=value', False),
            ('SUPABASE_SERVICE_ROLE_KEY=REPLACE_ME', False),
            ('eyJabc.abc.def', False),
            ((Path(__file__).parent.parent / '.env.example').read_text(), False),
        ]
        for index, (text, expected) in enumerate(cases):
            with self.subTest(case=index):
                self.assertEqual(bool(findings(text)), expected)

    def test_cli_exit_codes_and_redaction(self):
        scanner = Path(__file__).with_name('check_supabase_credentials.py')
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run(['git', 'init', '-q', directory], check=True)
            fixture = Path(directory) / 'fixture.txt'
            fixture.write_text(token('service_role'))
            subprocess.run(['git', '-C', directory, 'add', 'fixture.txt'], check=True)
            run = lambda path: subprocess.run(['python3', str(scanner), path], capture_output=True, text=True)
            result = run(directory)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn(token('service_role'), result.stdout + result.stderr)
            fixture.write_text('SUPABASE_JWT_SECRET=\n')
            self.assertEqual(run(directory).returncode, 0)
            self.assertEqual(run(directory + '/missing').returncode, 2)


class ProviderTests(unittest.TestCase):
    def test_signatures_and_redaction(self):
        cases = [('-----BEGIN ' + 'PRIVATE KEY-----', 'private-key'),
                 ('sk_' + 'live_' + 'a' * 24, 'stripe-secret'),
                 ('whsec_' + 'b' * 24, 'stripe-webhook'),
                 ('AK' + 'IA' + 'A' * 16, 'aws-access-key'),
                 ('gh' + 'p_' + 'c' * 30, 'github-token'),
                 ('S' + 'G.' + 'd' * 24 + '.' + 'e' * 24, 'sendgrid-key')]
        for secret, rule in cases:
            with self.subTest(rule=rule):
                self.assertIn((1, rule), findings(secret))
    def test_tracked_environment_file(self):
        scanner = Path(__file__).with_name('check_supabase_credentials.py')
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run(['git', 'init', '-q', directory], check=True)
            fixture = Path(directory) / '.env.test'
            fixture.write_text('PUBLIC_SETTING=synthetic')
            subprocess.run(['git', '-C', directory, 'add', '.env.test'], check=True)
            result = subprocess.run(['python3', str(scanner), directory], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('tracked-environment-file', result.stdout)
            self.assertNotIn('PUBLIC_SETTING', result.stdout)

if __name__ == '__main__':
    unittest.main()
