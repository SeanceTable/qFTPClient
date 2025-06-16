import unittest
import os
import tempfile
import ftplib
from unittest.mock import Mock, patch
import sys

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ftp_client_core import connect_ftp, upload_file, download_file, delete_file, rename_file, make_directory

class TestFTPClientCore(unittest.TestCase):
    """Unit tests for FTP client core functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_ftp = Mock(spec=ftplib.FTP)
        
    def test_connect_ftp_success(self):
        """Test successful FTP connection"""
        with patch('ftp_client_core.ftplib.FTP') as mock_ftp_class:
            mock_ftp_instance = Mock()
            mock_ftp_class.return_value = mock_ftp_instance
            
            result = connect_ftp("test.example.com", "testuser", "testpass")
            
            mock_ftp_instance.login.assert_called_once_with("testuser", "testpass")
            self.assertEqual(result, mock_ftp_instance)
    
    def test_connect_ftp_failure(self):
        """Test FTP connection failure"""
        with patch('ftp_client_core.ftplib.FTP') as mock_ftp_class:
            mock_ftp_instance = Mock()
            mock_ftp_class.return_value = mock_ftp_instance
            mock_ftp_instance.login.side_effect = ftplib.error_perm("Login failed")
            
            result = connect_ftp("test.example.com", "baduser", "badpass")
            
            self.assertIsNone(result)
    
    def test_upload_file(self):
        """Test file upload functionality"""
        # Create a temporary file for testing
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write("Test content")
            temp_file_path = temp_file.name
        
        try:
            # Mock the FTP storbinary method
            self.mock_ftp.storbinary = Mock()
            
            # Test upload
            upload_file(self.mock_ftp, temp_file_path, "remote_test.txt")
            
            # Verify storbinary was called
            self.mock_ftp.storbinary.assert_called_once()
            
        finally:
            # Clean up temporary file
            os.unlink(temp_file_path)
    
    def test_download_file(self):
        """Test file download functionality"""
        # Create a temporary file path for download
        temp_file_path = tempfile.mktemp()
        
        try:
            # Mock the FTP retrbinary method
            self.mock_ftp.retrbinary = Mock()
            
            # Test download
            download_file(self.mock_ftp, "remote_test.txt", temp_file_path)
            
            # Verify retrbinary was called
            self.mock_ftp.retrbinary.assert_called_once()
            
        finally:
            # Clean up if file was created
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
    
    def test_delete_file(self):
        """Test file deletion functionality"""
        self.mock_ftp.delete = Mock()
        
        delete_file(self.mock_ftp, "test_file.txt")
        
        self.mock_ftp.delete.assert_called_once_with("test_file.txt")
    
    def test_rename_file(self):
        """Test file renaming functionality"""
        self.mock_ftp.rename = Mock()
        
        rename_file(self.mock_ftp, "old_name.txt", "new_name.txt")
        
        self.mock_ftp.rename.assert_called_once_with("old_name.txt", "new_name.txt")
    
    def test_make_directory(self):
        """Test directory creation functionality"""
        self.mock_ftp.mkd = Mock()
        
        make_directory(self.mock_ftp, "new_folder")
        
        self.mock_ftp.mkd.assert_called_once_with("new_folder")

class TestGUIIntegration(unittest.TestCase):
    """Integration tests for GUI components"""
    
    def setUp(self):
        """Set up test fixtures for GUI tests"""
        # Note: GUI tests would require a display server in a real environment
        # These are simplified tests for demonstration
        pass
    
    def test_quick_connect_dialog_creation(self):
        """Test that Quick Connect dialog can be created"""
        # This would require PyQt5 and a display server
        # In a real test environment, you would test dialog creation and validation
        pass
    
    def test_site_manager_dialog_creation(self):
        """Test that Site Manager dialog can be created"""
        # This would require PyQt5 and a display server
        # In a real test environment, you would test dialog creation and site management
        pass

if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)

