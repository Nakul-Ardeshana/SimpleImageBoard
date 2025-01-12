import os

# Define the directory containing your files

directory = r"static\images"
directory= directory if os.path.exists(directory) else "images"
image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"}

def count_images_with_sidecars(directory):
    """Count and return the number of images that have a sidecar file."""
    count = 0
    for root, _, files in os.walk(directory):
        for file in files:
            # Check if the file is an image
            if os.path.splitext(file)[1].lower() in image_extensions:
                file_path = os.path.join(root, file)
                sidecar_path = f"{os.path.splitext(file_path)[0]}.txt"
                
                # Check if sidecar exists
                if os.path.exists(sidecar_path):
                    count += 1
    return count

# Run the function and print the result
images_with_sidecars = count_images_with_sidecars(directory)
print(f"Number of images with sidecars: {images_with_sidecars}")
input("Exit?")
