import os
import sys
import ctypes

HOSTS_FILE = r"C:\Windows\System32\drivers\etc\hosts"
DOMAIN = "steel.local"
IP = "127.0.0.1"


def _is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def is_domain_configured():
    try:
        with open(HOSTS_FILE, "r") as f:
            content = f.read()
            return DOMAIN in content
    except:
        return False


def add_domain():
    if is_domain_configured():
        print(f"{DOMAIN} already configured")
        return True
    
    if not _is_admin():
        print(f"Admin required to add {DOMAIN} to hosts file")
        print("Run as administrator or add manually:")
        print(f"  {IP}  {DOMAIN}")
        return False
    
    try:
        with open(HOSTS_FILE, "a") as f:
            f.write(f"\n{IP}  {DOMAIN}\n")
        print(f"Added {DOMAIN} to hosts file")
        return True
    except Exception as e:
        print(f"Error adding domain: {e}")
        return False


def remove_domain():
    if not is_domain_configured():
        print(f"{DOMAIN} not configured")
        return True
    
    if not _is_admin():
        print(f"Admin required to remove {DOMAIN} from hosts file")
        return False
    
    try:
        with open(HOSTS_FILE, "r") as f:
            lines = f.readlines()
        
        with open(HOSTS_FILE, "w") as f:
            for line in lines:
                if DOMAIN not in line:
                    f.write(line)
        
        print(f"Removed {DOMAIN} from hosts file")
        return True
    except Exception as e:
        print(f"Error removing domain: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "add":
            add_domain()
        elif sys.argv[1] == "remove":
            remove_domain()
        elif sys.argv[1] == "check":
            print(f"{DOMAIN} configured: {is_domain_configured()}")
    else:
        print(f"Usage: python hosts_manager.py [add|remove|check]")
