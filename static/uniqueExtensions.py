import os

def get_file_types(directory):
    file_types = set()
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_extension = os.path.splitext(file)[1]  # Get file extension
            if file_extension:  # Only add if there is an extension
                file_types.add(file_extension.lower())
    
    return file_types

# Usage
directory = r"static\images"
directory= directory if os.path.exists(directory) else "images"
file_types = get_file_types(directory)

print("Unique file types in directory:", file_types)
input("Exit?")

