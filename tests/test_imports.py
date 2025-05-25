"""
Basic tests to ensure the package can be imported and basic functionality works.
"""

import unittest
import sys
import os

# Add the parent directory to the path so we can import the package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestImports(unittest.TestCase):
    """Test that the package can be imported."""
    
    def test_import_package(self):
        """Test that the package can be imported."""
        try:
            import bib2graph
            self.assertTrue(True)
        except ImportError:
            self.fail("Failed to import the package")
    
    def test_import_main_classes(self):
        """Test that the main classes can be imported."""
        try:
            from bib2graph import BibliometricDataLoader
            from bib2graph import BibliometricDataEnricher
            from bib2graph import BibliometricNetworkAnalyzer
            self.assertTrue(True)
        except ImportError:
            self.fail("Failed to import main classes")
    
    def test_version(self):
        """Test that the version is defined."""
        import bib2graph
        self.assertIsNotNone(bib2graph.__version__)
        self.assertIsInstance(bib2graph.__version__, str)


if __name__ == '__main__':
    unittest.main()