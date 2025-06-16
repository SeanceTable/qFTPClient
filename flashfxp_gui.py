import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QTreeWidget, QTreeWidgetItem, QListWidget,
                             QListWidgetItem, QSplitter, QMenuBar, QStatusBar,
                             QToolBar, QAction, QLabel, QProgressBar, QTabWidget,
                             QPushButton, QMessageBox, QInputDialog) # Added QMessageBox, QInputDialog
from PyQt5.QtCore import Qt, QUrl # Added QUrl for local file system
from PyQt5.QtGui import QIcon, QColor # Added QColor for item background
import ftp_client_core # Import the ftp client core
from ftp_client_core import IntegrityCheckFailedError # Import custom exception
from dialogs import QuickConnectDialog, SiteManagerDialog # Import QuickConnectDialog and SiteManagerDialog
import ftplib # Add this line
class FlashFXPClone(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ftp_connection = None # Placeholder for actual FTP connection
        self.current_remote_path = "/" # Initialize current remote path
        self.local_tree_widget = None # Will be set in createFilePane
        self.local_file_list = None # Will be set in createFilePane
        self.remote_tree_widget = None # Will be set in createFilePane
        self.remote_file_list = None # Will be set in createFilePane
        self.current_transfer_settings = {'verify_integrity': False} # Store transfer settings
        self.initUI()
        
        # Populate local files on startup
        self.populate_local_files(os.path.expanduser("~"), self.local_tree_widget, self.local_file_list)


    def connect_to_ftp_server_detailed(self, details):
        host = details.get('host')
        port = details.get('port')
        username = details.get('username')
        password = details.get('password')
        # Map "None" from dialog to "FTP" for connect_server, or pass directly if different
        security_type = details.get('security', 'FTP')
        if security_type == "None": # From QuickConnectDialog
            security_type = "FTP"
        passive_mode = details.get('passive', True)
        self.current_transfer_settings['verify_integrity'] = details.get('verify_integrity', False)

        print(f"Attempting to connect via connect_server with details: {details}")
        try:
            self.statusBar().showMessage(f"Connecting to {host} ({security_type})...")
            self.ftp_connection = ftp_client_core.connect_server(
                host, port, username, password, security_type, passive_mode
            )

            if self.ftp_connection:
                self.statusBar().showMessage(f"Successfully connected to {host} ({security_type}).")
                print(f"Successfully connected to {host} ({security_type}).")
                self.current_remote_path = "/" # Reset remote path on new connection
                self.remote_tree_widget.clear() # Clear existing remote tree items
                self.remote_tree_widget.setHeaderLabel(f"Connected to {host}") # Update header
                # After successful connection, refresh the remote file list
                self.refresh_remote_files()
            else:
                self.statusBar().showMessage(f"Failed to connect to {host} ({security_type}).")
                print(f"Failed to connect to {host} ({security_type}).")
                QMessageBox.critical(self, "Connection Error", f"Failed to connect to {host} ({security_type}). Check details or server.")
        except Exception as e:
            self.statusBar().showMessage(f"Connection Error: {e}")
            QMessageBox.critical(self, "Connection Error", f"An error occurred during connection: {e}")


    def handle_connect_action(self):
        dialog = QuickConnectDialog(self)
        if dialog.exec_() == QuickConnectDialog.Accepted:
            details = dialog.get_connection_details()
            print(f"Quick Connect dialog accepted. Details: {details}")
            self.connect_to_ftp_server_detailed(details)
        else:
            print("Quick Connect dialog canceled.")

    def handle_site_manager_action(self):
        dialog = SiteManagerDialog(self)
        # In a real app, you'd pass existing site data to the dialog
        # and retrieve updated data when dialog is accepted.
        dialog.exec_() # For now, just show it.

    def handle_disconnect_action(self):
        if self.ftp_connection:
            try:
                ftp_client_core.disconnect_ftp(self.ftp_connection)
                self.ftp_connection = None
                self.statusBar().showMessage("Disconnected from server.")
                self.remote_tree_widget.clear()
                self.remote_tree_widget.setHeaderLabel("Site (Disconnected)")
                self.remote_file_list.clear()
                self.current_remote_path = "/"
            except Exception as e:
                QMessageBox.critical(self, "Disconnect Error", f"Error during disconnection: {e}")
                self.statusBar().showMessage(f"Error during disconnection: {e}")
        else:
            self.statusBar().showMessage("Not connected to any server.")

    def remote_directory_changed(self, current_item, previous_item):
        if current_item is None:
            # No item selected, or selection cleared. This might happen during refresh.
            return

        selected_dir_name = current_item.text(0)

        if selected_dir_name == "..":
            # Navigate up one level
            # Get the parent directory of the *current* remote path
            # os.path.normpath handles '..' and '.' correctly
            # os.path.split will correctly separate head/tail, and head is the parent
            head, tail = os.path.split(self.current_remote_path.rstrip('/'))
            
            # If head is empty after split (e.g., for '/'), it means we are at the root
            if not head:
                self.current_remote_path = '/'
            else:
                self.current_remote_path = head + '/'
            
            # Ensure path uses forward slashes, important for FTP
            self.current_remote_path = self.current_remote_path.replace('\\', '/')

        else:
            # Build path by traversing up from the current item to the root of the tree.
            path_parts = []
            item_iterator = current_item

            while item_iterator is not None:
                # Skip the root placeholder if it's the top-level server name
                # Check if it's the invisible root's child and its text matches the header
                if item_iterator.parent() is None and self.remote_tree_widget and \
                   self.remote_tree_widget.headerItem() and \
                   item_iterator.text(0) == self.remote_tree_widget.headerItem().text(0):
                    break # This is the top-level server name, not part of actual path
                
                # Exclude the ".." entry from path construction if it's not a real directory name
                if item_iterator.text(0) != "..":
                    path_parts.insert(0, item_iterator.text(0)) # Prepend to get correct order
                item_iterator = item_iterator.parent()

            # Construct the full path
            if not path_parts: # If only the header was clicked or no valid path parts
                self.current_remote_path = "/"
            else:
                # Join parts with '/', then normalize to clean up any redundant slashes
                # Ensure it starts with a slash and ends with a slash if it's a directory
                temp_path = "/" + "/".join(path_parts)
                self.current_remote_path = os.path.normpath(temp_path).replace('\\', '/')
                
                # Ensure it ends with a slash if it's not the root itself
                if not self.current_remote_path.endswith('/') and self.current_remote_path != '/':
                    self.current_remote_path += '/'
                
                # Special handling for Windows drive roots if any normalization resulted in a single backslash
                # This should be less necessary with .replace('\\', '/') but as a safeguard.
                if len(self.current_remote_path) > 1 and self.current_remote_path.startswith('/') and self.current_remote_path[1] == '/':
                    self.current_remote_path = self.current_remote_path[1:] # Remove leading double slash if it forms
                
                # Ensure the root is just '/'
                if self.current_remote_path == '//' or self.current_remote_path == '/.':
                    self.current_remote_path = '/'

        print(f"Remote directory changed to: {self.current_remote_path}")
        self.refresh_remote_files() # Refresh the file list for the new directory

    def initUI(self):
        self.setWindowTitle('FlashFXP Clone - Python FTP Client')
        self.setGeometry(100, 100, 1200, 800)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Create main layout
        main_layout = QVBoxLayout(central_widget)

        # Create menu bar
        self.createMenuBar()

        # Create toolbar
        self.createToolBar()

        # Create dual-pane file browser
        self.createDualPaneLayout(main_layout)

        # Create transfer queue
        self.createTransferQueue(main_layout)

        # Create status bar
        self.createStatusBar()

    def createMenuBar(self):
        menubar = self.menuBar()
        
        # Session menu
        session_menu = menubar.addMenu('Session')
        quick_connect_action = session_menu.addAction('Quick Connect')
        quick_connect_action.triggered.connect(self.handle_connect_action)
        
        site_manager_action = session_menu.addAction('Site Manager')
        site_manager_action.triggered.connect(self.handle_site_manager_action)
        
        session_menu.addSeparator()
        exit_action = session_menu.addAction('Exit')
        exit_action.triggered.connect(self.close)

        # Sites menu
        sites_menu = menubar.addMenu('Sites')
        sites_menu.addAction('Site Manager').triggered.connect(self.handle_site_manager_action)

        # Options menu
        options_menu = menubar.addMenu('Options')
        options_menu.addAction('Preferences')

        # Queue menu
        queue_menu = menubar.addMenu('Queue')
        queue_menu.addAction('Start').triggered.connect(self.startUpload)
        queue_menu.addAction('Clear').triggered.connect(self.clearQueue)
        queue_menu.addAction('Remove Selected').triggered.connect(self.removeSelected)

        # Commands menu
        commands_menu = menubar.addMenu('Commands')
        commands_menu.addAction('Raw Command')

        # Tools menu
        tools_menu = menubar.addMenu('Tools')
        tools_menu.addAction('Server File Search')

        # Directory menu
        directory_menu = menubar.addMenu('Directory')
        refresh_action = directory_menu.addAction('Refresh')
        refresh_action.triggered.connect(self.refresh_remote_files) # Hook up refresh
        create_folder_action = directory_menu.addAction('Create Folder (Remote)')
        create_folder_action.triggered.connect(self.create_remote_folder)


        # View menu
        view_menu = menubar.addMenu('View')
        view_menu.addAction('Transfer Graph')
        view_menu.addAction('Single Connection Layout')

        # Help menu
        help_menu = menubar.addMenu('Help')
        help_menu.addAction('About')

    def createToolBar(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)

        # Add toolbar actions
        connect_action = QAction(QIcon.fromTheme("network-connect"), "Connect", self) # Assuming icons are available or remove QIcon
        connect_action.triggered.connect(self.handle_connect_action)
        toolbar.addAction(connect_action)

        disconnect_action = QAction(QIcon.fromTheme("network-disconnect"), "Disconnect", self)
        disconnect_action.triggered.connect(self.handle_disconnect_action) # Implement later
        toolbar.addAction(disconnect_action)
        toolbar.addSeparator()
        
        upload_action = QAction(QIcon.fromTheme("go-up"), "Upload Selected", self)
        upload_action.triggered.connect(self.upload_selected_local_files)
        toolbar.addAction(upload_action)

        download_action = QAction(QIcon.fromTheme("go-down"), "Download Selected", self)
        download_action.triggered.connect(self.download_selected_remote_files)
        toolbar.addAction(download_action)

        toolbar.addSeparator()
        refresh_action = QAction(QIcon.fromTheme("view-refresh"), "Refresh", self)
        refresh_action.triggered.connect(self.refresh_remote_files)
        toolbar.addAction(refresh_action)
        
        delete_action = QAction(QIcon.fromTheme("edit-delete"), "Delete", self)
        delete_action.triggered.connect(self.delete_selected_file_or_dir)
        toolbar.addAction(delete_action)

        rename_action = QAction(QIcon.fromTheme("document-edit"), "Rename", self)
        rename_action.triggered.connect(self.rename_selected_file_or_dir)
        toolbar.addAction(rename_action)

    def createDualPaneLayout(self, main_layout):
        # Create horizontal splitter for dual panes
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # Left pane (Local)
        # Pass references to store the widgets
        left_pane_widget, self.local_tree_widget, self.local_file_list = self.createFilePane("Local Browser", "My Computer", is_local=True)
        splitter.addWidget(left_pane_widget)

        # Right pane (Remote)
        right_pane_widget, self.remote_tree_widget, self.remote_file_list = self.createFilePane("Site", "Not Connected", is_local=False)
        splitter.addWidget(right_pane_widget)

        # Connect remote tree widget's current item changed signal
        self.remote_tree_widget.currentItemChanged.connect(self.remote_directory_changed)
        # Connect local tree widget's current item changed signal to populate local file list
        self.local_tree_widget.currentItemChanged.connect(self.local_directory_changed)


        # Set equal sizes for both panes
        splitter.setSizes([600, 600])

    def createFilePane(self, title, root_name, is_local=True):
        pane_widget = QWidget()
        pane_layout = QVBoxLayout(pane_widget)

        # Pane title
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: bold; padding: 5px; background-color: #e0e0e0;")
        pane_layout.addWidget(title_label)

        # Create tree widget for folder navigation
        tree_widget = QTreeWidget()
        tree_widget.setHeaderLabel(root_name)
        tree_widget.setMaximumHeight(150) # Keep folders view compact
        
        pane_layout.addWidget(tree_widget)

        # Create list widget for file listing
        file_list = QListWidget()
        if is_local:
            file_list.setDragEnabled(True) # Enable drag for local files
            self.local_file_list = file_list # Store reference
            self.local_tree_widget = tree_widget # Store reference
        else:
            self.remote_file_list = file_list # Store reference
            self.remote_tree_widget = tree_widget # Store reference
            
        pane_layout.addWidget(file_list)

        # Status info
        status_label = QLabel("0 Files, 0 Folders, 0 Total (0 MB)") # Will update dynamically
        status_label.setStyleSheet("padding: 5px; background-color: #f0f0f0; font-size: 10px;")
        pane_layout.addWidget(status_label)

        return pane_widget, tree_widget, file_list # Return all three for external access


    def createTransferQueue(self, main_layout):
        # Create transfer queue section
        queue_widget = QTabWidget()
        queue_widget.setMaximumHeight(200)
        
        # Queue tab
        queue_tab = QWidget()
        queue_layout = QVBoxLayout(queue_tab)
        
        # Transfer list
        self.transfer_list = QListWidget() # Made it an instance variable
        self.transfer_list.setAcceptDrops(True)
        self.transfer_list.dragEnterEvent = self.dragEnterEvent
        self.transfer_list.dragMoveEvent = self.dragMoveEvent
        self.transfer_list.dropEvent = self.dropEvent

        queue_layout.addWidget(self.transfer_list)

        # Add Queue Management Buttons
        button_layout = QHBoxLayout()
        self.btn_start_upload = QPushButton("Start Upload")
        self.btn_start_upload.clicked.connect(self.startUpload)
        self.btn_clear_queue = QPushButton("Clear Queue")
        self.btn_clear_queue.clicked.connect(self.clearQueue)
        self.btn_remove_selected = QPushButton("Remove Selected")
        self.btn_remove_selected.clicked.connect(self.removeSelected)

        button_layout.addWidget(self.btn_start_upload)
        button_layout.addWidget(self.btn_clear_queue)
        button_layout.addWidget(self.btn_remove_selected)
        queue_layout.addLayout(button_layout)
        
        # Progress bar
        self.transfer_progress_bar = QProgressBar() # Make it an instance variable
        self.transfer_progress_bar.setValue(0)
        queue_layout.addWidget(self.transfer_progress_bar)
        
        # Transfer status
        self.transfer_status_label = QLabel("Ready") # Make it an instance variable
        self.transfer_status_label.setStyleSheet("font-size: 10px; padding: 2px;")
        queue_layout.addWidget(self.transfer_status_label)
        
        queue_widget.addTab(queue_tab, "Queue")
        
        # Log tab
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        self.log_list = QListWidget() # Make log list an instance variable
            
        log_layout.addWidget(self.log_list)
        queue_widget.addTab(log_tab, "Log")
        
        main_layout.addWidget(queue_widget)

    def createStatusBar(self):
        status_bar = self.statusBar()
        status_bar.showMessage("Ready")

    # File System Population Methods
    def populate_local_files(self, path, tree_widget, file_list_widget):
        tree_widget.clear()
        file_list_widget.clear()

        root_item = QTreeWidgetItem(tree_widget, [os.path.basename(path) if path != "/" else "Computer"])
        root_item.setExpanded(True)
        tree_widget.addTopLevelItem(root_item)
        
        self._add_local_directories_recursive(path, root_item)
        self._add_local_files_to_list(path, file_list_widget)

    def _add_local_directories_recursive(self, parent_path, parent_item):
        try:
            for entry in os.listdir(parent_path):
                full_path = os.path.join(parent_path, entry)
                if os.path.isdir(full_path):
                    dir_item = QTreeWidgetItem(parent_item, [entry])
                    # We won't pre-populate sub-directories, but expand later on demand
                    # For a simple demo, you could expand one level, but it can be slow for large trees.
        except PermissionError:
            print(f"Permission denied for: {parent_path}")
        except Exception as e:
            print(f"Error listing local directory {parent_path}: {e}")

    def _add_local_files_to_list(self, path, file_list_widget):
        try:
            for entry in os.listdir(path):
                full_path = os.path.join(path, entry)
                if os.path.isfile(full_path):
                    item = QListWidgetItem(entry)
                    item.setData(Qt.UserRole, full_path) # Store full path
                    file_list_widget.addItem(item)
        except PermissionError:
            print(f"Permission denied for: {path}")
        except Exception as e:
            print(f"Error listing local files {path}: {e}")

    def local_directory_changed(self, current_item, previous_item):
        if current_item is None:
            return

        path_parts = []
        item_iterator = current_item
        while item_iterator is not None:
            path_parts.insert(0, item_iterator.text(0))
            item_iterator = item_iterator.parent()
        
        # Reconstruct full path for the local system
        # Handle Windows drive letters, C:\Users\..., or Unix /home/...
        if sys.platform == "win32":
            if len(path_parts) > 1 and len(path_parts[0]) == 1 and path_parts[0].isalpha(): # e.g., C:\
                current_local_path = path_parts[0] + ":\\" + "\\".join(path_parts[1:])
            else: # For paths like "My Documents" which are relative or user-specific
                # This needs to be more robust. For simplicity, assume user's home for now.
                current_local_path = os.path.join(os.path.expanduser("~"), *path_parts[1:])
                # Or handle a fixed root if "My Computer" is literal
                if path_parts[0] == "My Computer":
                    current_local_path = os.path.expanduser("~") # Or system root like '/' or 'C:\'
                else:
                    current_local_path = os.path.join(os.path.expanduser("~"), *path_parts) # Simplistic fallback
                current_local_path = os.path.normpath(current_local_path)
        else: # Unix-like systems
            current_local_path = "/" + "/".join(path_parts)
            if current_local_path == "/My Computer": # Adjust for initial display name
                current_local_path = "/"
            current_local_path = os.path.normpath(current_local_path)

        if os.path.isdir(current_local_path):
            self._add_local_files_to_list(current_local_path, self.local_file_list)
            # You might want to clear and re-populate the tree's children here
            # to show expanded subdirectories if not already done.
        else:
            self.local_file_list.clear() # Clear if a file or non-existent path is selected

    def refresh_remote_files(self):
        if not self.ftp_connection:
            self.statusBar().showMessage("Not connected to refresh remote files.")
            self.remote_file_list.clear()
            self.remote_tree_widget.clear()
            self.remote_tree_widget.setHeaderLabel("Site (Disconnected)")
            return

        self.remote_file_list.clear()
        self.remote_tree_widget.clear()
        self.remote_tree_widget.setHeaderLabel(self.ftp_connection.__class__.__name__) # Show connection type

        try:
            # For FTP, change directory first to ensure accurate listing of current_remote_path
            if isinstance(self.ftp_connection, ftplib.FTP):
                self.ftp_connection.cwd(self.current_remote_path)
            
            dir_contents = ftp_client_core.list_directory(self.ftp_connection, self.current_remote_path)
            
            # Create root item for the remote tree, representing the current path
            root_item_name = self.current_remote_path if self.current_remote_path != '/' else '/'
            root_item = QTreeWidgetItem(self.remote_tree_widget, [root_item_name])
            root_item.setExpanded(True)
            self.remote_tree_widget.addTopLevelItem(root_item)
            
            # Populate files and folders
            folders_count = 0
            files_count = 0
            total_size = 0

            # Add a ".." (parent directory) entry if not at root
            if self.current_remote_path != '/':
                parent_dir_item = QTreeWidgetItem(root_item, [".."])
                parent_dir_item.setData(0, Qt.UserRole, "dir") 
                parent_dir_item.setForeground(0, QColor(Qt.blue)) # Indicate navigability
                folders_count += 1
            
            for entry in dir_contents:
                name = entry['name']
                file_type = entry['type']
                size = entry['size']

                if file_type == 'dir':
                    dir_item = QTreeWidgetItem(root_item, [name])
                    dir_item.setData(0, Qt.UserRole, "dir") 
                    dir_item.setForeground(0, QColor(Qt.blue)) # Indicate navigability
                    folders_count += 1
                else: # file
                    file_item = QListWidgetItem(name)
                    file_item.setData(Qt.UserRole, "file") # Store type
                    file_item.setData(Qt.UserRole + 1, size) # Store size
                    self.remote_file_list.addItem(file_item)
                    files_count += 1
                    total_size += size
            
            self.statusBar().showMessage(f"Refreshed remote directory: {self.current_remote_path}")
            # Update status label on the remote pane (not currently linked, but good to add if you create a dedicated label)
            # self.remote_status_label.setText(f"{files_count} Files, {folders_count} Folders, {files_count + folders_count} Total ({total_size / (1024*1024):.2f} MB)")

        except Exception as e:
            self.statusBar().showMessage(f"Failed to refresh remote directory: {e}")
            QMessageBox.critical(self, "Refresh Error", f"Could not refresh remote directory '{self.current_remote_path}': {e}")


    # Button logic implementations
    def startUpload(self):
        print("Start Upload clicked")
        if not self.ftp_connection:
            QMessageBox.warning(self, "Upload Error", "Not connected to any FTP/SFTP server.")
            self.transfer_status_label.setText("Upload failed: Not connected.")
            return

        items_to_process_snapshot = []
        for i in range(self.transfer_list.count()):
            items_to_process_snapshot.append(self.transfer_list.item(i))

        if not items_to_process_snapshot:
            self.transfer_status_label.setText("Queue is empty. Nothing to upload.")
            return

        self.transfer_progress_bar.setValue(0)
        self.transfer_status_label.setText("Starting uploads...")

        for item_index, item in enumerate(items_to_process_snapshot):
            try:
                text = item.text()
                # Assuming format: "local_path -> remote_path_base/"
                parts = text.split(" -> ")
                if len(parts) < 2:
                    raise ValueError("Invalid queue item format.")
                
                local_path = parts[0].strip()
                remote_base_path = parts[1].strip().rstrip('/') # Remove trailing slash for joining

                file_name = os.path.basename(local_path)
                # Construct the full remote path for the file
                actual_remote_path = f"{remote_base_path}/{file_name}"
                
                self.transfer_status_label.setText(f"Uploading: {file_name}...")
                self.transfer_progress_bar.setValue(int((item_index / len(items_to_process_snapshot)) * 100))


                try:
                    # Actual FTP upload call, now with integrity check option
                    ftp_client_core.upload_file(
                        self.ftp_connection,
                        local_path,
                        actual_remote_path,
                        verify_integrity=self.current_transfer_settings.get('verify_integrity', False)
                    )
                    print(f"FTP Upload call processed for: {local_path} to {actual_remote_path}")
                    self.log_list.addItem(f"[Success] Uploaded: {file_name} to {actual_remote_path}")
                    # If successful, remove the item. Important: work with snapshot then remove by actual item
                    # Find the current index of the item (it might have shifted if previous items were removed)
                    current_item_row = self.transfer_list.row(item)
                    if current_item_row != -1: # Ensure it's still in the list
                        self.transfer_list.takeItem(current_item_row)
                    
                except IntegrityCheckFailedError as icfe:
                    print(f"GUI: Integrity Check FAILED for {file_name}: {icfe}")
                    item.setText(f"{text} [Checksum Mismatch]")
                    item.setBackground(QColor("red")) # Basic visual feedback
                    self.log_list.addItem(f"[FAIL] Checksum Mismatch for {file_name}: {icfe}")
                    # Item remains in queue, marked.
                except Exception as e_upload: # Other upload errors
                    print(f"GUI: Upload FAILED for {file_name}: {e_upload}")
                    item.setText(f"{text} [Upload Error]")
                    item.setBackground(QColor("lightcoral")) # Different color for other errors
                    self.log_list.addItem(f"[ERROR] Upload failed for {file_name}: {e_upload}")
                    # Item remains in queue, marked.

            except ValueError as ve:
                print(f"Error parsing item text: {text}. Expected format 'local_path -> remote_path_placeholder'. {ve}")
                item.setText(f"{text} [Bad Format]") # Mark item
                item.setBackground(QColor("orange"))
                self.log_list.addItem(f"[ERROR] Bad format for item: {text} - {ve}")
            except Exception as e_outer: # Catch-all for other unexpected issues in the loop
                print(f"An unexpected error occurred while processing item {text}: {e_outer}")
                if item: # If item reference is valid
                    item.setText(f"{text} [Processing Error]")
                    item.setBackground(QColor("purple"))
                self.log_list.addItem(f"[ERROR] Unexpected error processing {text}: {e_outer}")

        self.transfer_progress_bar.setValue(100)
        self.transfer_status_label.setText("Uploads completed.")
        self.refresh_remote_files() # Refresh remote view after uploads


    def clearQueue(self):
        print("Clear Queue clicked")
        self.transfer_list.clear()
        self.transfer_status_label.setText("Queue cleared.")
        self.transfer_progress_bar.setValue(0)

    def removeSelected(self):
        print("Remove Selected clicked")
        selected_items = self.transfer_list.selectedItems()
        if not selected_items:
            print("No items selected to remove.")
            return
        for item in selected_items:
            self.transfer_list.takeItem(self.transfer_list.row(item))
        print(f"{len(selected_items)} item(s) removed from queue.")
        self.transfer_status_label.setText(f"{len(selected_items)} item(s) removed from queue.")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.acceptProposedAction()
            
            for url in event.mimeData().urls():
                local_path = url.toLocalFile()
                if os.path.exists(local_path):
                    # For a directory, you might want to add all its contents recursively
                    # For now, just add the directory itself as an item, or its files.
                    if os.path.isfile(local_path):
                        # Use current remote path from the remote tree selection
                        remote_path = self.current_remote_path
                        item_text = f"{local_path} -> {remote_path}"
                        QListWidgetItem(item_text, self.transfer_list)
                        self.log_list.addItem(f"[Queue] Added: {local_path} for upload to {remote_path}")
                    elif os.path.isdir(local_path):
                        # Optionally, if a directory is dragged, add all its files to queue
                        QMessageBox.information(self, "Drag & Drop", f"Dragged directory: {local_path}. Not recursively adding contents yet. Drag individual files.")
                else:
                    self.log_list.addItem(f"[ERROR] Invalid local path dragged: {local_path}")
        else:
            event.ignore()

    def upload_selected_local_files(self):
        """Adds selected local files directly to the queue and starts upload."""
        selected_items = self.local_file_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "Upload", "No local files selected for upload.")
            return
        
        if not self.ftp_connection:
            QMessageBox.warning(self, "Upload Error", "Not connected to any FTP/SFTP server.")
            return

        for item in selected_items:
            local_path = item.data(Qt.UserRole) # Retrieve full path
            if local_path:
                remote_path = self.current_remote_path
                item_text = f"{local_path} -> {remote_path}"
                QListWidgetItem(item_text, self.transfer_list)
                self.log_list.addItem(f"[Queue] Added via button: {local_path} for upload to {remote_path}")
        
        self.startUpload() # Automatically start upload

    def download_selected_remote_files(self):
        """Initiates download of selected remote files."""
        selected_items = self.remote_file_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "Download", "No remote files selected for download.")
            return

        if not self.ftp_connection:
            QMessageBox.warning(self, "Download Error", "Not connected to any FTP/SFTP server.")
            return
        
        # Ask user for local download directory
        download_dir = QFileDialog.getExistingDirectory(self, "Select Download Directory", os.path.expanduser("~"))
        if not download_dir:
            return # User cancelled

        for item in selected_items:
            file_name = item.text()
            remote_path = os.path.join(self.current_remote_path, file_name).replace("\\", "/")
            local_path = os.path.join(download_dir, file_name)

            self.transfer_status_label.setText(f"Downloading: {file_name}...")
            self.log_list.addItem(f"[Download] Starting: {remote_path} to {local_path}")
            try:
                ftp_client_core.download_file(self.ftp_connection, remote_path, local_path, 
                                              verify_integrity=self.current_transfer_settings.get('verify_integrity', False))
                self.log_list.addItem(f"[Success] Downloaded: {file_name}")
                self.statusBar().showMessage(f"Downloaded {file_name} to {local_path}")
            except IntegrityCheckFailedError as icfe:
                self.log_list.addItem(f"[FAIL] Download Checksum Mismatch for {file_name}: {icfe}")
                QMessageBox.warning(self, "Download Failed", f"Integrity check failed for {file_name}.")
            except Exception as e:
                self.log_list.addItem(f"[ERROR] Download failed for {file_name}: {e}")
                QMessageBox.critical(self, "Download Error", f"Failed to download {file_name}: {e}")
        
        self.transfer_status_label.setText("Downloads completed.")


    def delete_selected_file_or_dir(self):
        """Deletes selected file/directory from either local or remote pane."""
        if self.local_file_list.selectedItems():
            selected_item = self.local_file_list.selectedItems()[0]
            file_path = selected_item.data(Qt.UserRole)
            if QMessageBox.question(self, "Delete Local", f"Are you sure you want to delete local file: {os.path.basename(file_path)}?",
                                     QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        self.log_list.addItem(f"[Action] Deleted local file: {file_path}")
                    elif os.path.isdir(file_path):
                        # Requires shutil.rmtree for non-empty directories, or rmdir for empty
                        # For simplicity, will just try rmdir for now
                        os.rmdir(file_path) 
                        self.log_list.addItem(f"[Action] Deleted local directory: {file_path}")
                    self.populate_local_files(os.path.dirname(file_path), self.local_tree_widget, self.local_file_list) # Refresh local view
                    self.statusBar().showMessage(f"Deleted local: {os.path.basename(file_path)}")
                except Exception as e:
                    QMessageBox.critical(self, "Local Delete Error", f"Failed to delete local: {e}")
                    self.log_list.addItem(f"[ERROR] Failed to delete local {file_path}: {e}")

        elif self.remote_file_list.selectedItems():
            if not self.ftp_connection:
                QMessageBox.warning(self, "Delete Remote", "Not connected to server.")
                return

            selected_item = self.remote_file_list.selectedItems()[0]
            item_name = selected_item.text()
            item_type = selected_item.data(Qt.UserRole) # 'file' or 'dir'
            remote_path_to_delete = os.path.join(self.current_remote_path, item_name).replace("\\", "/")

            if QMessageBox.question(self, "Delete Remote", f"Are you sure you want to delete remote {item_type}: {item_name}?",
                                     QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                try:
                    if item_type == 'file':
                        ftp_client_core.delete_file(self.ftp_connection, remote_path_to_delete)
                        self.log_list.addItem(f"[Action] Deleted remote file: {remote_path_to_delete}")
                    elif item_type == 'dir':
                        # FTP_TLS.rmd() for directories
                        if isinstance(self.ftp_connection, ftplib.FTP):
                            self.ftp_connection.rmd(remote_path_to_delete)
                        elif ftp_client_core.paramiko_available and isinstance(self.ftp_connection, paramiko.SFTPClient):
                             self.ftp_connection.rmdir(remote_path_to_delete)
                        else:
                             raise TypeError("Unsupported client type for directory deletion.")
                        self.log_list.addItem(f"[Action] Deleted remote directory: {remote_path_to_delete}")
                    self.statusBar().showMessage(f"Deleted remote: {item_name}")
                    self.refresh_remote_files()
                except Exception as e:
                    QMessageBox.critical(self, "Remote Delete Error", f"Failed to delete remote: {e}")
                    self.log_list.addItem(f"[ERROR] Failed to delete remote {remote_path_to_delete}: {e}")
        else:
            QMessageBox.information(self, "Delete", "Please select an item to delete in either local or remote pane.")


    def rename_selected_file_or_dir(self):
        """Renames selected file/directory from either local or remote pane."""
        if self.local_file_list.selectedItems():
            selected_item = self.local_file_list.selectedItems()[0]
            old_name = selected_item.text()
            old_path = selected_item.data(Qt.UserRole)

            new_name, ok = QInputDialog.getText(self, "Rename Local", f"Rename '{old_name}' to:", text=old_name)
            if ok and new_name:
                new_path = os.path.join(os.path.dirname(old_path), new_name)
                try:
                    os.rename(old_path, new_path)
                    self.log_list.addItem(f"[Action] Renamed local from {old_path} to {new_path}")
                    self.populate_local_files(os.path.dirname(old_path), self.local_tree_widget, self.local_file_list) # Refresh local view
                    self.statusBar().showMessage(f"Renamed local: {old_name} to {new_name}")
                except Exception as e:
                    QMessageBox.critical(self, "Local Rename Error", f"Failed to rename local: {e}")
                    self.log_list.addItem(f"[ERROR] Failed to rename local {old_path}: {e}")

        elif self.remote_file_list.selectedItems():
            if not self.ftp_connection:
                QMessageBox.warning(self, "Rename Remote", "Not connected to server.")
                return

            selected_item = self.remote_file_list.selectedItems()[0]
            old_name = selected_item.text()
            remote_old_path = os.path.join(self.current_remote_path, old_name).replace("\\", "/")

            new_name, ok = QInputDialog.getText(self, "Rename Remote", f"Rename '{old_name}' to:", text=old_name)
            if ok and new_name:
                remote_new_path = os.path.join(self.current_remote_path, new_name).replace("\\", "/")
                try:
                    ftp_client_core.rename_file(self.ftp_connection, remote_old_path, remote_new_path)
                    self.log_list.addItem(f"[Action] Renamed remote from {remote_old_path} to {remote_new_path}")
                    self.statusBar().showMessage(f"Renamed remote: {old_name} to {new_name}")
                    self.refresh_remote_files()
                except Exception as e:
                    QMessageBox.critical(self, "Remote Rename Error", f"Failed to rename remote: {e}")
                    self.log_list.addItem(f"[ERROR] Failed to rename remote {remote_old_path}: {e}")
        else:
            QMessageBox.information(self, "Rename", "Please select an item to rename in either local or remote pane.")

    def create_remote_folder(self):
        if not self.ftp_connection:
            QMessageBox.warning(self, "Create Folder Remote", "Not connected to server.")
            return
        
        folder_name, ok = QInputDialog.getText(self, "Create Remote Folder", "Enter new folder name:")
        if ok and folder_name:
            full_remote_path = os.path.join(self.current_remote_path, folder_name).replace("\\", "/")
            try:
                ftp_client_core.make_directory(self.ftp_connection, full_remote_path)
                self.log_list.addItem(f"[Action] Created remote folder: {full_remote_path}")
                self.statusBar().showMessage(f"Created remote folder: {folder_name}")
                self.refresh_remote_files()
            except Exception as e:
                QMessageBox.critical(self, "Create Folder Error", f"Failed to create remote folder: {e}")
                self.log_list.addItem(f"[ERROR] Failed to create remote folder {full_remote_path}: {e}")


def main():
    app = QApplication(sys.argv)
    window = FlashFXPClone()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()