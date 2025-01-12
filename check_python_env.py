import os
import sys
import subprocess

# Paths
script_dir = os.path.dirname(os.path.abspath(__file__))
venv_dir = os.path.join(script_dir, "env")
python_version_file = os.path.join(script_dir, "python_version.txt")

def get_current_python_version():
    """Gets the current Python version as a string."""
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

def read_saved_python_version():
    """Reads the saved Python version from the version file."""
    if not os.path.exists(python_version_file):
        return None
    with open(python_version_file, "r") as file:
        return file.read().strip()

def save_python_version(version):
    """Saves the current Python version to the version file."""
    with open(python_version_file, "w") as file:
        file.write(version)

def delete_virtual_environment():
    """Deletes the virtual environment directory."""
    if os.path.exists(venv_dir):
        print(f"Deleting the existing virtual environment at {venv_dir}...")
        if os.name == 'nt':
            subprocess.run(["rmdir", "/S", "/Q", venv_dir], shell=True)
        else:
            subprocess.run(["rm", "-rf", venv_dir])

def create_virtual_environment():
    """Creates a new virtual environment."""
    print(f"Creating a new virtual environment at {venv_dir}...")
    subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)

def main():
    current_version = get_current_python_version()
    print(f"Current Python Version: {current_version}")

    saved_version = read_saved_python_version()
    if saved_version:
        print(f"Saved Python Version: {saved_version}")
    else:
        print("No saved Python version found. Assuming first run.")

    if not saved_version or saved_version != current_version:
        print("Python version has changed or is missing.")
        delete_virtual_environment()
        save_python_version(current_version)

    if not os.path.exists(venv_dir):
        create_virtual_environment()
    else:
        print("Virtual environment already exists. No need to recreate.")

if __name__ == "__main__":
    main()
