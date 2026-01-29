import subprocess
import sys


def main():
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "--version"])
    except Exception:
        subprocess.check_call([sys.executable, "-m", "ensurepip", "--upgrade"])

    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])


if __name__ == "__main__":
    main()
