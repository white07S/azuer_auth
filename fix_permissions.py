#!/usr/bin/env python3
"""
Script to diagnose and fix permission issues with the sessions directory
"""

import os
import sys
import shutil
from pathlib import Path
import subprocess
import pwd
import grp

def get_user_info():
    """Get current user information"""
    uid = os.getuid()
    gid = os.getgid()
    user = pwd.getpwuid(uid).pw_name
    group = grp.getgrgid(gid).gr_name
    return uid, gid, user, group

def check_directory_permissions(path):
    """Check permissions on a directory"""
    if not path.exists():
        print(f"❌ Directory does not exist: {path}")
        return False

    try:
        stat_info = os.stat(path)
        permissions = oct(stat_info.st_mode)[-3:]
        owner_uid = stat_info.st_uid
        owner_gid = stat_info.st_gid

        try:
            owner_user = pwd.getpwuid(owner_uid).pw_name
            owner_group = grp.getgrgid(owner_gid).gr_name
        except:
            owner_user = str(owner_uid)
            owner_group = str(owner_gid)

        current_uid, current_gid, current_user, current_group = get_user_info()

        print(f"📁 Directory: {path}")
        print(f"   Permissions: {permissions}")
        print(f"   Owner: {owner_user}:{owner_group} ({owner_uid}:{owner_gid})")
        print(f"   Current user: {current_user}:{current_group} ({current_uid}:{current_gid})")

        # Check if we can write to the directory
        test_file = path / ".test_write_permission"
        try:
            test_file.touch()
            test_file.unlink()
            print(f"   ✅ Write permission: Yes")
            return True
        except PermissionError:
            print(f"   ❌ Write permission: No")
            return False
        except Exception as e:
            print(f"   ❌ Write test failed: {e}")
            return False

    except Exception as e:
        print(f"❌ Error checking directory: {e}")
        return False

def fix_permissions(path, create_if_missing=True):
    """Fix permissions on a directory"""
    try:
        if not path.exists() and create_if_missing:
            print(f"Creating directory: {path}")
            path.mkdir(parents=True, exist_ok=True, mode=0o777)

        if path.exists():
            # Change ownership to current user if we have permission
            current_uid, current_gid, _, _ = get_user_info()
            try:
                os.chown(path, current_uid, current_gid)
                print(f"✅ Changed ownership to current user")
            except PermissionError:
                print(f"⚠️  Cannot change ownership (need sudo)")

            # Set full permissions
            os.chmod(path, 0o777)
            print(f"✅ Set permissions to 777")

            # Also fix permissions on subdirectories
            for subdir in path.iterdir():
                if subdir.is_dir():
                    try:
                        os.chmod(subdir, 0o777)
                        print(f"   ✅ Fixed permissions on {subdir.name}")
                    except:
                        print(f"   ⚠️  Could not fix permissions on {subdir.name}")

            return True
    except Exception as e:
        print(f"❌ Failed to fix permissions: {e}")
        return False

def use_alternative_location():
    """Set up alternative session directory in /tmp"""
    alt_dir = Path(f"/tmp/auth_azure_sessions_{os.getuid()}")
    print(f"\n🔄 Setting up alternative session directory: {alt_dir}")

    try:
        alt_dir.mkdir(parents=True, exist_ok=True, mode=0o777)
        os.chmod(alt_dir, 0o777)
        print(f"✅ Created alternative directory with full permissions")

        # Update .env file if it exists
        env_file = Path("backend/.env")
        if env_file.exists():
            print(f"\n📝 Update your .env file with:")
            print(f"   SESSION_DIR={alt_dir}")
            print(f"   # or")
            print(f"   ALT_SESSION_DIR={alt_dir}")

        return alt_dir
    except Exception as e:
        print(f"❌ Failed to create alternative directory: {e}")
        return None

def main():
    print("🔍 Azure Auth Sessions Permission Fixer\n")
    print("=" * 50)

    # Check default sessions directory
    default_session_dir = Path("./sessions")
    backend_session_dir = Path("./backend/sessions")

    print("\n📋 Checking default session directories:\n")

    can_write_default = check_directory_permissions(default_session_dir)
    print()
    can_write_backend = check_directory_permissions(backend_session_dir)

    if not can_write_default and not can_write_backend:
        print("\n⚠️  Cannot write to either default location")

        # Try to fix permissions
        print("\n🔧 Attempting to fix permissions...")

        if os.path.exists("./backend"):
            target_dir = backend_session_dir
        else:
            target_dir = default_session_dir

        if fix_permissions(target_dir):
            print(f"\n✅ Fixed permissions on {target_dir}")
        else:
            print(f"\n⚠️  Could not fix permissions on {target_dir}")

            # Try with sudo
            print("\n💡 Try running with sudo:")
            print(f"   sudo python3 fix_permissions.py")
            print("\n   OR use an alternative location:")

            alt_dir = use_alternative_location()
            if alt_dir:
                print(f"\n✅ Alternative directory ready: {alt_dir}")
                print(f"\n🚀 Start the backend with:")
                print(f"   SESSION_DIR={alt_dir} python main.py")
    else:
        print("\n✅ Permissions look good!")
        if can_write_default:
            print(f"   Using: {default_session_dir}")
        else:
            print(f"   Using: {backend_session_dir}")

    # Check if Azure CLI is installed
    print("\n📋 Checking Azure CLI installation:")
    try:
        result = subprocess.run(["az", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print("   ✅ Azure CLI is installed")
            version_lines = result.stdout.split('\n')
            if version_lines:
                print(f"   {version_lines[0]}")
        else:
            print("   ❌ Azure CLI check failed")
    except FileNotFoundError:
        print("   ❌ Azure CLI not found. Install it with:")
        print("      curl -L https://aka.ms/InstallAzureCli | bash")

    print("\n" + "=" * 50)
    print("✨ Done!")

if __name__ == "__main__":
    main()