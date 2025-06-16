import sys
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
                             QLineEdit, QPushButton, QLabel, QComboBox, 
                             QCheckBox, QSpinBox, QTabWidget, QWidget,
                             QTreeWidget, QTreeWidgetItem, QGroupBox,
                             QDialogButtonBox, QMessageBox, QTextEdit, QAction, 
                             QFileDialog, QMainWindow) # QMainWindow, QTextEdit, QAction, QFileDialog explicitly added
from PyQt5.QtCore import Qt, QDir # QDir explicitly added
from PyQt5.QtGui import QFont, QIcon # QFont, QIcon explicitly added
import json # Added for session saving
import os   # Added for session saving and file path handling

# Define a simple path for the session file
SESSION_FILE = 'last_session.json'

class QuickConnectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Quick Connect')
        self.setFixedSize(400, 300)
        self.initUI()
        self.load_last_session() # Load session on initialization

    def initUI(self):
        layout = QVBoxLayout(self)

        # Connection details form
        form_layout = QFormLayout()
        
        self.host_edit = QLineEdit()
        self.host_edit.setPlaceholderText('ftp.example.com')
        form_layout.addRow('Host:', self.host_edit)

        self.username_edit = QLineEdit()
        form_layout.addRow('Username:', self.username_edit)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        form_layout.addRow('Password:', self.password_edit)

        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(21)
        form_layout.addRow('Port:', self.port_spin)

        layout.addLayout(form_layout)

        # Connection options
        options_group = QGroupBox('Connection Options')
        options_layout = QVBoxLayout(options_group)
        
        self.passive_check = QCheckBox('Use passive mode')
        self.passive_check.setChecked(True)
        options_layout.addWidget(self.passive_check)

        self.secure_combo = QComboBox()
        self.secure_combo.addItems(['None', 'FTPS (SSL/TLS)', 'SFTP (SSH)'])
        options_layout.addWidget(QLabel('Security:'))
        options_layout.addWidget(self.secure_combo)

        self.integrity_check_check = QCheckBox("Verify file integrity (FTP/FTPS)")
        self.integrity_check_check.setChecked(False) # Default to off
        options_layout.addWidget(self.integrity_check_check)

        layout.addWidget(options_group)

        # Buttons
        button_layout = QHBoxLayout()
        self.connect_btn = QPushButton('Connect')
        self.cancel_btn = QPushButton('Cancel')
        
        self.connect_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.connect_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

    def get_connection_details(self):
        return {
            'host': self.host_edit.text(),
            'username': self.username_edit.text(),
            'password': self.password_edit.text(),
            'port': self.port_spin.value(),
            'passive': self.passive_check.isChecked(),
            'security': self.secure_combo.currentText(),
            'verify_integrity': self.integrity_check_check.isChecked()
        }

    def load_last_session(self):
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, 'r') as f:
                    details = json.load(f)
                self.host_edit.setText(details.get('host', ''))
                self.username_edit.setText(details.get('username', ''))
                self.password_edit.setText(details.get('password', ''))
                self.port_spin.setValue(details.get('port', 21))
                self.passive_check.setChecked(details.get('passive', True))
                index = self.secure_combo.findText(details.get('security', 'None'))
                if index != -1:
                    self.secure_combo.setCurrentIndex(index)
                self.integrity_check_check.setChecked(details.get('verify_integrity', False))
            except Exception as e:
                print(f"Error loading last session: {e}")

    def save_last_session(self, details):
        try:
            with open(SESSION_FILE, 'w') as f:
                json.dump(details, f)
        except Exception as e:
            print(f"Error saving last session: {e}")

class SiteManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Site Manager')
        self.setFixedSize(800, 600)
        self.initUI()

    def initUI(self):
        layout = QHBoxLayout(self)

        # Left side - Site list
        left_layout = QVBoxLayout()
        
        sites_label = QLabel('Sites:')
        left_layout.addWidget(sites_label)
        
        self.sites_tree = QTreeWidget()
        self.sites_tree.setHeaderLabel('Site Name')
        self.sites_tree.setMaximumWidth(250)
        
        # Add sample sites
        root = QTreeWidgetItem(self.sites_tree, ['My Sites'])
        work_folder = QTreeWidgetItem(root, ['Work'])
        QTreeWidgetItem(work_folder, ['Production Server'])
        QTreeWidgetItem(work_folder, ['Staging Server'])
        
        personal_folder = QTreeWidgetItem(root, ['Personal'])
        QTreeWidgetItem(personal_folder, ['Home FTP'])
        QTreeWidgetItem(personal_folder, ['Backup Server'])
        
        self.sites_tree.expandAll()
        left_layout.addWidget(self.sites_tree)
        
        # Site management buttons
        site_buttons_layout = QHBoxLayout()
        new_site_btn = QPushButton('New Site')
        delete_site_btn = QPushButton('Delete')
        duplicate_btn = QPushButton('Duplicate')
        
        site_buttons_layout.addWidget(new_site_btn)
        site_buttons_layout.addWidget(delete_site_btn)
        site_buttons_layout.addWidget(duplicate_btn)
        left_layout.addLayout(site_buttons_layout)
        
        layout.addLayout(left_layout)

        # Right side - Site configuration
        right_layout = QVBoxLayout()
        
        # Tabs for different configuration sections
        tabs = QTabWidget()
        
        # General tab
        general_tab = QWidget()
        general_layout = QFormLayout(general_tab)
        
        self.site_name_edit = QLineEdit('Production Server')
        general_layout.addRow('Site Name:', self.site_name_edit)
        
        self.host_edit = QLineEdit('ftp.mycompany.com')
        general_layout.addRow('Host:', self.host_edit)
        
        self.username_edit = QLineEdit('myusername')
        general_layout.addRow('Username:', self.username_edit)
        
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        general_layout.addRow('Password:', self.password_edit)
        
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(21)
        general_layout.addRow('Port:', self.port_spin)
        
        tabs.addTab(general_tab, 'General')
        
        # Connection tab
        connection_tab = QWidget()
        connection_layout = QVBoxLayout(connection_tab)
        
        connection_group = QGroupBox('Connection Mode')
        connection_group_layout = QVBoxLayout(connection_group)
        
        self.passive_check = QCheckBox('Use passive mode (recommended)')
        self.passive_check.setChecked(True)
        connection_group_layout.addWidget(self.passive_check)
        
        connection_layout.addWidget(connection_group)
        
        security_group = QGroupBox('Security')
        security_layout = QFormLayout(security_group)
        
        self.security_combo = QComboBox()
        self.security_combo.addItems(['None', 'FTPS (SSL/TLS)', 'SFTP (SSH)'])
        security_layout.addRow('Protocol:', self.security_combo)
        
        connection_layout.addWidget(security_group)
        connection_layout.addStretch()
        
        tabs.addTab(connection_tab, 'Connection')
        
        # Options tab
        options_tab = QWidget()
        options_layout = QVBoxLayout(options_tab)
        
        transfer_group = QGroupBox('Transfer Options')
        transfer_layout = QVBoxLayout(transfer_group)
        
        self.auto_resume_check = QCheckBox('Automatically resume failed transfers')
        self.auto_resume_check.setChecked(True)
        transfer_layout.addWidget(self.auto_resume_check)
        
        self.binary_mode_check = QCheckBox('Use binary mode for all transfers')
        transfer_layout.addWidget(self.binary_mode_check)

        self.integrity_check_check = QCheckBox("Verify file integrity after transfer (FTP/FTPS only)")
        self.integrity_check_check.setChecked(False) # Default to off
        transfer_layout.addWidget(self.integrity_check_check)
        
        options_layout.addWidget(transfer_group)
        options_layout.addStretch()
        
        tabs.addTab(options_tab, 'Options')
        
        right_layout.addWidget(tabs)
        layout.addLayout(right_layout)

        # Bottom buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addWidget(button_box)
        
        self.setLayout(main_layout)

# NEW CLASS: Text Editor Dialog
class TextEditorDialog(QMainWindow): # QMainWindow explicitly imported from QtWidgets at top
    def __init__(self, parent=None, file_path=None, is_remote=False, ftp_client=None, remote_current_path=None):
        super().__init__(parent)
        self.file_path = file_path # Local path for the temp file (if remote), or actual local file
        self.is_remote = is_remote
        self.ftp_client = ftp_client # The connected FTP/SFTP client object
        self.remote_current_path = remote_current_path # Remote directory path
        self.original_remote_file_name = os.path.basename(file_path) if is_remote else None # Original name on server

        self.setWindowTitle(f"Editing: {self.original_remote_file_name or os.path.basename(file_path) or 'New File'}")
        self.setGeometry(200, 200, 800, 600)
        self.initUI()
        self.load_file_content()

    def initUI(self):
        self.text_edit = QTextEdit()
        self.text_edit.setFont(QFont("Consolas", 10)) # Monospaced font for code/text editing
        self.setCentralWidget(self.text_edit)

        # File Menu
        file_menu = self.menuBar().addMenu('&File')
        
        save_action = QAction('&Save', self)
        save_action.setShortcut('Ctrl+S')
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)

        close_action = QAction('&Close', self)
        close_action.setShortcut('Ctrl+W')
        close_action.triggered.connect(self.close)
        file_menu.addAction(close_action)

    def load_file_content(self):
        # We need ftp_client_core here to download/upload
        try:
            # Import ftp_client_core directly inside the method to ensure it's available
            # This is a robust way to ensure it's loaded when this dialog needs it.
            import ftp_client_core 
        except ImportError:
            QMessageBox.critical(self, "Error", "ftp_client_core module not found. Cannot edit files.")
            self.text_edit.setText("ERROR: ftp_client_core module not loaded. Cannot load file content.")
            return

        if self.file_path:
            try:
                if self.is_remote and self.ftp_client and self.remote_current_path:
                    # Download remote file to a temporary local file for editing
                    temp_dir = QDir.tempPath()
                    temp_file_name = self.original_remote_file_name
                    self.local_temp_file_path = os.path.join(temp_dir, temp_file_name)
                    
                    # Ensure the temp directory exists
                    if not QDir().exists(temp_dir):
                        QDir().mkpath(temp_dir)

                    remote_full_path = os.path.join(self.remote_current_path, self.original_remote_file_name).replace('\\', '/')
                    
                    try:
                        ftp_client_core.download_file(self.ftp_client, remote_full_path, self.local_temp_file_path)
                    except Exception as e:
                        raise IOError(f"Failed to download remote file: {e}")
                    
                    with open(self.local_temp_file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    self.text_edit.setText(content)
                    self.setWindowTitle(f"Editing (Remote): {self.original_remote_file_name}")
                elif not self.is_remote and os.path.exists(self.file_path):
                    with open(self.file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    self.text_edit.setText(content)
                    self.setWindowTitle(f"Editing (Local): {os.path.basename(self.file_path)}")
                else:
                    self.text_edit.setText("Error: File not found or no remote connection.")
                    self.setWindowTitle("New File")
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Could not load file: {e}")
                self.text_edit.setText(f"Error loading file: {e}")
                self.setWindowTitle(f"Error: {self.original_remote_file_name or os.path.basename(self.file_path)}")

    def save_file(self):
        content = self.text_edit.toPlainText()
        try:
            import ftp_client_core # Import here for the dialog's function.
            if self.is_remote and self.ftp_client and self.remote_current_path:
                # Save content to the temporary local file first
                with open(self.local_temp_file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                # Then upload the temporary file to overwrite the remote file
                remote_full_path = os.path.join(self.remote_current_path, self.original_remote_file_name).replace('\\', '/')
                ftp_client_core.upload_file(self.ftp_client, self.local_temp_file_path, remote_full_path)
                QMessageBox.information(self, "Save Successful", f"Remote file '{self.original_remote_file_name}' saved.")
                self.text_edit.document().setModified(False) # Mark as saved
            elif not self.is_remote and self.file_path:
                with open(self.file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                QMessageBox.information(self, "Save Successful", f"Local file '{os.path.basename(self.file_path)}' saved.")
                self.text_edit.document().setModified(False) # Mark as saved
            else:
                QMessageBox.warning(self, "Save Error", "Cannot save: No valid file path or connection.")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save file: {e}")

    def closeEvent(self, event):
        # Ask to save if changes were made
        if self.text_edit.document().isModified():
            reply = QMessageBox.question(self, 'Save Changes?',
                                         "Do you want to save changes to this file?",
                                         QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if reply == QMessageBox.Yes:
                self.save_file()
                event.accept()
            elif reply == QMessageBox.No:
                event.accept()
            else:
                event.ignore() # Do not close
        else:
            event.accept() # Close directly

        # Clean up temporary file if it was a remote edit
        if self.is_remote and hasattr(self, 'local_temp_file_path') and os.path.exists(self.local_temp_file_path):
            try:
                os.remove(self.local_temp_file_path)
                print(f"Cleaned up temporary file: {self.local_temp_file_path}")
            except Exception as e:
                print(f"Error cleaning up temporary file {self.local_temp_file_path}: {e}")

# Test the dialogs
if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Test Quick Connect
    quick_connect = QuickConnectDialog()
    if quick_connect.exec_() == QDialog.Accepted:
        details = quick_connect.get_connection_details()
        print("Quick Connect Details:", details)
    
    # Test Site Manager
    site_manager = SiteManagerDialog()
    site_manager.exec_()
    
    # Test Text Editor (standalone, for local file)
    # editor_dialog = TextEditorDialog(file_path="test_local_file.txt", is_remote=False)
    # editor_dialog.show()

    sys.exit(app.exec_())