import ftplib
from ftplib import FTP_TLS # For FTPS
import hashlib # For MD5 checksums
import os # For os.path.basename and os.walk
import io # For in-memory file for SFTP list_directory parsing

# Attempt to import paramiko and set a flag
paramiko_available = False
try:
    import paramiko # For SFTP
    paramiko_available = True
except ImportError:
    print("Warning: paramiko module not found. SFTP functionality will be disabled.")

class IntegrityCheckFailedError(Exception):
    """Custom exception for MD5 checksum mismatch."""
    pass

def connect_plain_ftp(host, port=21, username=None, password=None, passive_mode=True):
    try:
        ftp = ftplib.FTP()
        ftp.connect(host, port)
        if username and password: # Allow anonymous FTP if no user/pass
            ftp.login(username, password)
        else:
            ftp.login() # Anonymous login
        ftp.set_pasv(passive_mode)
        print(f"Successfully connected via plain FTP to {host} as {username or 'anonymous'}")
        return ftp
    except ftplib.all_errors as e:
        print(f"Plain FTP Error: {e}")
        return None

def connect_ftps(host, port=21, username=None, password=None, passive_mode=True):
    try:
        ftps = FTP_TLS()
        ftps.connect(host, port)
        if username and password:
            ftps.login(username, password)
        else:
            ftps.login() # Anonymous login
        ftps.prot_p()  # Secure data connection
        ftps.set_pasv(passive_mode)
        print(f"Successfully connected via FTPS to {host} as {username or 'anonymous'}")
        return ftps
    except ftplib.all_errors as e:
        print(f"FTPS Error: {e}")
        return None

def connect_sftp(host, port=22, username=None, password=None):
    transport = None
    try:
        transport = paramiko.Transport((host, port))
        transport.connect(username=username, password=password)
        sftp = paramiko.SFTPClient.from_transport(transport)
        print(f"Successfully connected via SFTP to {host} as {username}")
        return sftp
    except paramiko.AuthenticationException as e:
        print(f"SFTP Authentication Error: {e}")
        return None
    except paramiko.SSHException as e:
        print(f"SFTP SSH Error: {e}")
        return None
    except Exception as e: # Catch other potential errors like socket errors
        print(f"SFTP General Error: {e}")
        return None
    # Note: paramiko transport needs to be closed if SFTPClient.from_transport fails
    # or when the sftp session is done. This is typically handled by the caller
    # by closing the sftp client, which in turn should close the transport.

def connect_server(host, port, username, password, security_type="FTP", passive_mode=True):
    """
    Primary connection function to dispatch to specific protocol connectors.
    Port defaults are handled by individual connectors if not provided by caller.
    """
    print(f"connect_server called with: host={host}, port={port}, user={username}, sec={security_type}, passive={passive_mode}")

    # Ensure port is an integer
    try:
        port = int(port) if port else None # Default to None if empty or 0, let connectors handle defaults
    except ValueError:
        print(f"Invalid port value: {port}. Using default for protocol.")
        port = None

    if security_type == "None" or security_type == "FTP": # "None" comes from QuickConnectDialog
        # Use default port 21 if not specified
        actual_port = port if port is not None else 21
        return connect_plain_ftp(host, actual_port, username, password, passive_mode)
    elif security_type == "FTPS (SSL/TLS)":
        # Use default port 21 for explicit FTPS (can also be 990 for implicit, but FTP_TLS usually starts plain then secures)
        actual_port = port if port is not None else 21
        return connect_ftps(host, actual_port, username, password, passive_mode)
    elif security_type == "SFTP (SSH)":
        # Use default port 22 if not specified
        actual_port = port if port is not None else 22
        if not paramiko_available:
            print("SFTP (SSH) selected, but paramiko module is not available.")
            return None
        return connect_sftp(host, actual_port, username, password)
    else:
        print(f"Unsupported security type: {security_type}")
        return None

def disconnect_ftp(client):
    if client:
        try:
            if isinstance(client, ftplib.FTP): # Handles FTP and FTP_TLS
                client.quit()
                print("Disconnected from FTP/FTPS server.")
            elif paramiko_available and isinstance(client, paramiko.SFTPClient):
                # Ensure the transport is closed to clean up connections
                if client.get_transport():
                    client.get_transport().close()
                client.close() # Closes SFTP session
                print("Disconnected from SFTP server.")
            else:
                print("Unknown client type for disconnect.")
        except Exception as e:
            print(f"Error during disconnect: {e}")


def list_directory(client, path="."):
    """
    Lists directory contents for connected client.
    Returns a list of dictionaries, each with 'name', 'type' ('file'/'dir'), 'size' (for files).
    """
    if not client:
        print("Cannot list directory: No connection available.")
        return []

    entries = []
    try:
        if isinstance(client, ftplib.FTP): # Handles FTP and FTP_TLS
            # Use a list to capture output of dir()
            lines = []
            client.dir(path, lines.append)
            
            for line in lines:
                parts = line.split()
                if len(parts) < 9: # Basic check for valid line format
                    continue
                
                permissions = parts[0]
                name = " ".join(parts[8:]) # Name can contain spaces

                file_type = 'file'
                if permissions.startswith('d'):
                    file_type = 'dir'
                
                size = 0
                if file_type == 'file' and parts[4].isdigit():
                    size = int(parts[4])

                entries.append({'name': name, 'type': file_type, 'size': size})

        elif paramiko_available and isinstance(client, paramiko.SFTPClient):
            for entry_attr in client.listdir_attr(path):
                name = entry_attr.filename
                # Skip . and .. entries
                if name in ('.', '..'):
                    continue

                file_type = 'file'
                size = entry_attr.st_size if hasattr(entry_attr, 'st_size') else 0

                # Paramiko's SFTPAtrrs has methods to check file types
                if entry_attr.longname.startswith('d'): # More robust check for directory
                    file_type = 'dir'
                # Alternatively, paramiko.stat.S_ISDIR(entry_attr.st_mode)
                
                entries.append({'name': name, 'type': file_type, 'size': size})
        else:
            print("Cannot list directory: Unsupported client type.")
    except Exception as e:
        print(f"Error listing directory '{path}': {e}")
    
    return entries


def calculate_local_md5(filepath):
    """Calculates the MD5 checksum of a local file."""
    md5_hash = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()
    except FileNotFoundError:
        print(f"Error: Local file not found at {filepath} for MD5 calculation.")
        return None
    except Exception as e:
        print(f"Error calculating local MD5 for {filepath}: {e}")
        return None

def get_remote_md5_ftp(client, remote_path):
    """Attempts to get MD5 hash of a remote file using XMD5 or MD5 commands for FTP/FTPS."""
    if not isinstance(client, ftplib.FTP): # Also covers FTP_TLS
        print("Remote MD5 check (XMD5/MD5 command) is only supported for FTP/FTPS clients.")
        return None

    md5_hash = None
    try:
        # Try XMD5 first
        response = client.sendcmd('XMD5 ' + remote_path)
        # Response typically "213 <hash>" or "<hash>" for some servers on 2xx success
        # For ProFTPD, it's "250 <hash>"
        if response.startswith(('213 ', '250 ')): # Check for common success codes
            md5_hash = response.split()[-1]
        elif len(response.split()) == 1 and len(response) == 32 and all(c in '0123456789abcdefABCDEF' for c in response): # Raw hash
             md5_hash = response
        else: # Fallback for unexpected positive responses, try to extract if it looks like a hash
            parts = response.split()
            if parts and len(parts[-1]) == 32 and all(c in '0123456789abcdefABCDEF' for c in parts[-1]):
                 md5_hash = parts[-1]

    except ftplib.error_perm as e_perm: # Command not supported or file not found (5xx)
        print(f"XMD5 command failed for {remote_path}: {e_perm}. Trying MD5 command.")
        try:
            response = client.sendcmd('MD5 ' + remote_path)
            if response.startswith(('213 ', '250 ')):
                md5_hash = response.split()[-1]
            elif len(response.split()) == 1 and len(response) == 32 and all(c in '0123456789abcdefABCDEF' for c in response):
                 md5_hash = response
            else:
                parts = response.split()
                if parts and len(parts[-1]) == 32 and all(c in '0123456789abcdefABCDEF' for c in parts[-1]):
                     md5_hash = parts[-1]
        except ftplib.error_perm as e_perm_md5:
            print(f"MD5 command also failed for {remote_path}: {e_perm_md5}")
        except Exception as e_md5: # Other errors for MD5 command
            print(f"Error executing MD5 command for {remote_path}: {e_md5}")
    except Exception as e: # Other errors for XMD5 command
        print(f"Error executing XMD5 command for {remote_path}: {e}")

    if md5_hash and len(md5_hash) == 32 and all(c in '0123456789abcdefABCDEF' for c in md5_hash.lower()):
        return md5_hash.lower()
    else:
        if md5_hash: # Got something but it doesn't look like an MD5
            print(f"Warning: Received non-standard MD5 response for {remote_path}: {response}")
        return None


def upload_file(client, local_path, remote_path, verify_integrity=False):
    if not client:
        print("Upload Error: No connection available.")
        raise ConnectionError("No FTP/SFTP connection available.")

    try:
        if isinstance(client, ftplib.FTP): # Handles FTP and FTP_TLS
            with open(local_path, 'rb') as f:
                client.storbinary(f'STOR {remote_path}', f)
            print(f"Successfully uploaded (FTP/FTPS) {local_path} to {remote_path}")

            if verify_integrity:
                print(f"Verifying integrity of {remote_path}...")
                local_md5 = calculate_local_md5(local_path)
                remote_md5 = get_remote_md5_ftp(client, remote_path)
                print(f"Local MD5: {local_md5}, Remote MD5: {remote_md5}")
                if local_md5 and remote_md5:
                    if local_md5 == remote_md5:
                        print(f"Integrity check PASSED for {remote_path}.")
                    else:
                        raise IntegrityCheckFailedError(f"Integrity check FAILED for {remote_path}. Local MD5: {local_md5}, Remote MD5: {remote_md5}")
                else:
                    print(f"Warning: Could not verify integrity for {remote_path} due to missing MD5 hash(es). Server might not support XMD5/MD5 command.")

        elif paramiko_available and isinstance(client, paramiko.SFTPClient):
            client.put(local_path, remote_path) # SFTP does its own integrity checks by default in most implementations
            print(f"Successfully uploaded (SFTP) {local_path} to {remote_path}")
            if verify_integrity:
                 print("Note: SFTP upload includes inherent integrity checks. Manual MD5 check not typically performed for SFTP via this client.")
        else:
            print(f"Upload Error: Unsupported client type for {local_path}")
            raise TypeError("Unsupported client type for upload.")
    except IntegrityCheckFailedError as icfe:
        # Re-raise so GUI can catch it
        raise icfe
    except Exception as e: # Catches ftplib.all_errors and paramiko exceptions
        print(f"Upload Error for {local_path} to {remote_path}: {e}")
        raise IOError(f"Upload failed: {e}")


def download_file(client, remote_path, local_path, verify_integrity=False):
    if not client:
        print("Download Error: No connection available.")
        return

    remote_md5_for_check = None
    if verify_integrity and isinstance(client, ftplib.FTP): # FTP/FTPS
        print(f"Attempting to get remote MD5 for {remote_path} before download...")
        remote_md5_for_check = get_remote_md5_ftp(client, remote_path)
        if not remote_md5_for_check:
            print(f"Warning: Could not retrieve remote MD5 for {remote_path}. Will skip integrity check.")
        else:
            print(f"Remote MD5 for {remote_path} is {remote_md5_for_check}.")

    try:
        if isinstance(client, ftplib.FTP): # Handles FTP and FTP_TLS
            with open(local_path, 'wb') as f:
                client.retrbinary(f'RETR {remote_path}', f.write)
            print(f"Successfully downloaded (FTP/FTPS) {remote_path} to {local_path}")

            if verify_integrity and remote_md5_for_check: # Only if we got remote MD5 earlier
                print(f"Verifying integrity of downloaded file {local_path}...")
                local_md5 = calculate_local_md5(local_path)
                print(f"Local MD5: {local_md5}, Expected Remote MD5: {remote_md5_for_check}")
                if local_md5 and remote_md5_for_check: # Should always have remote_md5_for_check here
                    if local_md5 == remote_md5_for_check:
                        print(f"Integrity check PASSED for {local_path}.")
                    else:
                        raise IntegrityCheckFailedError(f"Integrity check FAILED for {local_path}. Local MD5: {local_md5}, Expected Remote MD5: {remote_md5_for_check}")
                else: # local_md5 failed
                    print(f"Warning: Could not calculate local MD5 for {local_path}. Integrity check skipped.")

        elif paramiko_available and isinstance(client, paramiko.SFTPClient):
            client.get(remote_path, local_path) # SFTP does its own integrity checks
            print(f"Successfully downloaded (SFTP) {remote_path} to {local_path}")
            if verify_integrity:
                print("Note: SFTP download includes inherent integrity checks. Manual MD5 check not typically performed for SFTP via this client.")
        else:
            print(f"Download Error: Unsupported client type for {remote_path}")
    except IntegrityCheckFailedError as icfe:
        print(f"Error: {icfe}") # Propagate or handle as needed
        # Potentially delete local file if integrity check fails? os.remove(local_path)
    except Exception as e:
        print(f"Download Error for {remote_path} to {local_path}: {e}")


def delete_file(client, remote_path):
    if not client:
        print("Delete Error: No connection available.")
        return
    try:
        if isinstance(client, ftplib.FTP):
            client.delete(remote_path)
            print(f"Successfully deleted (FTP/FTPS) {remote_path}")
        elif paramiko_available and isinstance(client, paramiko.SFTPClient):
            client.remove(remote_path)
            print(f"Successfully deleted (SFTP) {remote_path}")
        else:
            print(f"Delete Error: Unsupported client type for {remote_path}")
    except Exception as e:
        print(f"Delete Error for {remote_path}: {e}")


def rename_file(client, from_path, to_path):
    if not client:
        print("Rename Error: No connection available.")
        return
    try:
        if isinstance(client, ftplib.FTP):
            client.rename(from_path, to_path)
            print(f"Successfully renamed (FTP/FTPS) {from_path} to {to_path}")
        elif paramiko_available and isinstance(client, paramiko.SFTPClient):
            client.posix_rename(from_path, to_path) # SFTP often uses posix_rename
            print(f"Successfully renamed (SFTP) {from_path} to {to_path}")
        else:
            print(f"Rename Error: Unsupported client type for {from_path}")
    except Exception as e:
        print(f"Rename Error for {from_path} to {to_path}: {e}")


def make_directory(client, dir_name):
    if not client:
        print("Make Directory Error: No connection available.")
        return
    try:
        if isinstance(client, ftplib.FTP):
            client.mkd(dir_name)
            print(f"Successfully created directory (FTP/FTPS) {dir_name}")
        elif paramiko_available and isinstance(client, paramiko.SFTPClient):
            client.mkdir(dir_name)
            print(f"Successfully created directory (SFTP) {dir_name}")
        else:
            print(f"Make Directory Error: Unsupported client type for {dir_name}")
    except Exception as e:
        print(f"Make Directory Error for {dir_name}: {e}")