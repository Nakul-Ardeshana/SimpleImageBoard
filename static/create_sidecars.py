import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

# Define the directory containing your files
directory = r"static\images"
directory= directory if os.path.exists(directory) else "images"
image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"}

def get_files_without_sidecars(directory):
    """Return a list of image files without existing sidecar files."""
    files_to_process = []
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            # Check if the file is an image and does not have a sidecar
            if os.path.splitext(file)[1].lower() in image_extensions:
                sidecar_path = f"{os.path.splitext(file_path)[0]}.txt"
                if not os.path.exists(sidecar_path):  # Only add if sidecar doesn't exist
                    files_to_process.append(file_path)
    return files_to_process

def extract_and_write_tags(file_path):
    """Extract IPTC keywords using ExifTool and write to sidecar if tags are found."""
    command = f'exiftool -IPTC:Keywords -sep ";" "{file_path}"'
    result = subprocess.run(command, capture_output=True, text=True, shell=True)
    tags = result.stdout.strip()

    # Only create sidecar if tags are found
    if tags:
        sidecar_path = f"{os.path.splitext(file_path)[0]}.txt"
        with open(sidecar_path, 'w') as sidecar:
            for tag in tags.split(';'):
                sidecar.write(f"{tag.strip()}\n")
        return f"Tags extracted for {file_path}"
    return None

def main():
    # Gather files without sidecars
    files_without_sidecars = get_files_without_sidecars(directory)
    
    # Run the extraction and tagging in parallel with a progress bar
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Initialize tqdm progress bar
        with tqdm(total=len(files_without_sidecars), desc="Processing images", unit="file") as pbar:
            futures = {executor.submit(extract_and_write_tags, file): file for file in files_without_sidecars}
            for future in futures:
                result = future.result()
                if result:
                    print(result)
                pbar.update(1)

if __name__ == "__main__":
    main()
    input("Exit?")
