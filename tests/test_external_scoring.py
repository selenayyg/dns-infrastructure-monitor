import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from external_dns_checker import puan_hesapla, login_tespit

class ExternalTests(unittest.TestCase):
    def test_fast_200(self): self.assertEqual(puan_hesapla(200, 100, False, 'Açık'), 100)
    def test_timeout(self): self.assertEqual(puan_hesapla(None, None, False, 'Zaman Aşımı'), 0)
    def test_login(self): self.assertTrue(login_tespit('<form><input type="password"></form>')[0])

if __name__ == '__main__': unittest.main()
