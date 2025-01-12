# SimpleImageBoard

## Overview

SimpleImageBoard is a local server application for managing and searching a personal collection of images and their associated metadata. The project organizes images with sidecar files containing tags and allows advanced search functionality through a database-backed query system. The setup process is fully automated with a batch script.

---

## Features

- **Image Tagging**: Automatically associates images with tags from sidecar files.
- **Advanced Search**: Supports complex queries with AND, OR, NOT conditions, and "user:favorites."
- **Caching**: Frequently used queries are cached for faster access.
- **Database Management**: Efficient storage and indexing of image metadata.
- **Automation**: A batch script sets up the environment, processes files, and launches the search tool.

---

## Prerequisites

- Python 3.8 or later
- SQLite
- Windows (for `.bat` script execution)

Ensure Python is installed and available in your system's PATH.

---

## Installation and Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/Nakul-Ardeshana/SimpleImageBoard.git
   cd simpleimageboard
   ```
2. **Run the Batch Script**:
   Double-click on `simpleimageboard.bat` or execute it from the command line:
   ```
   simpleimageboard.bat
   ```
   This script:
   - Checks and sets up the Python virtual environment.
   - Installs required dependencies from `requirements.txt`.
   - Processes images and sidecars into the database.
   - Optionally verifies database integrity.

---

## File Structure

```
project_folder/
|-- Images_searcher.py       # Main search script
|-- db_utils.py              # Database utilities
|-- taginDB.py               # Database initialization and tagging
|-- simpleimageboard.bat     # Automation script
|-- requirements.txt         # Python dependencies
|-- static/
    |-- images/              # Image folder (place files here)
    |-- create_sidecars.py   # Utility for generating sidecar files
|-- templates/
    |-- index.html           # Frontend template
    |-- search.html          # Search page
```

---

## Usage

1. Place your images in the `static/images/` folder.
2. Ensure each image has an associated sidecar file with tags (one tag per line).
3. Run the batch script (`simpleimageboard.bat`) to process the files.
4. Use the search tool launched by `Images_searcher.py` to query your image database.

---

## Demo Video
Watch the demo video to see the setup and basic launch of the app:

[![SimpleImageBoard Demo](https://img.youtube.com/vi/CdtaZATEQpk/0.jpg)](https://www.youtube.com/watch?v=CdtaZATEQpk)

---

## Supported Queries

- **AND Conditions**: Separate tags with spaces (` `).
- **OR Conditions**: Separate tags with a pipe (`|`).
- **NOT Conditions**: Prefix tags with a dash (`-`).
- **Favorites**: Use `user:favorites` for searching or excluding favorites.

---

## Contributing

Contributions are welcome! Feel free to submit issues or pull requests to improve the project.

---

## Future Updates
I am actively working to improve SimpleImageBoard by resolving errors and adding new, useful features. This project is continually evolving to meet the needs of its users and to enhance functionality.

Please note that changes have already been made since the recording of the demo video. The latest version of the app includes additional improvements and bug fixes, which are not reflected in the video.

Stay tuned for updates, and feel free to suggest features or report issues through the repository!

---

## License

[GPL-2.0 license](LICENSE)

---

## File Descriptions

### db_utils.py

This module focuses on the database backend. It performs operations for managing image metadata and tags.

**Key Features:**

- **Database Initialization**: Creates tables for storing tags, tag counts, and favorite images.
- **Tag Management**:
  - Insert, update, and delete tags for images.
  - Count and fetch all unique tags in the database.
- **Image Metadata Management**:
  - Store and retrieve metadata like image paths and associated tags.
  - Support for adding and removing favorite images.
- **Query Caching**: Uses a JSON file (`cached_queries.json`) to store search query results for faster repeated access.
- **Advanced Search**: Provides functions to handle AND, OR, and NOT conditions for image search queries.

**Key Functions:**

- `initialize_database()`: Sets up the database tables if they don't already exist.
- `fetch_tags_with_id(image_path)`: Fetches tags and ID for a specific image.
- `upsert_tags(image_path, new_tags)`: Inserts or updates tags for an image.
- `delete_image(image_path)`: Deletes an image from the database and the filesystem.
- `search_images_with_conditions(search_query, onlyids=False)`: Performs complex searches with support for logical operators and wildcards.
- `fetch_all_tag_counts()`: Retrieves all tags and their counts.

**Dependencies:**

- `sqlite3`: For database operations.
- `os`, `json`, `re`: For file and query handling.

---

### Images_searcher.py

This module provides the Flask-based web interface and routes for interacting with the system.

**Key Features:**

- **Server Initialization**:
  - Supports both local-only and network-accessible modes.
  - Dynamic IP address determination for network mode.
- **Web Routes**:
  - `/`: Home page with a search bar and navigation.
  - `/allofthem`: Displays all images with pagination.
  - `/search/<searchTags>`: Searches images based on tags using advanced logic.
  - `/favorites`: Lists all favorited images.
  - `/result/<id>`: Displays details of a specific image.
  - `/delete/<id>`: Deletes an image by ID.
  - `/edit/<id>`: Updates tags for an image.
- **Autocomplete**: Suggests tags based on user input using `/autocomplete`.
- **Tag Co-occurrence Analysis**: Suggests related tags based on search results.
- **Pagination**: Efficiently handles large image collections by limiting images per page.

**Key Functions:**

- `index()`: Renders the home page.
- `search(searchTags, page=1)`: Handles tag-based image search with pagination.
- `allofthem(page=1)`: Displays all images with pagination.
- `edit_tags(id)`: Updates the tags for a specific image.
- `favorites(page=1)`: Displays the user's favorite images.

**Templates and Static Files:**

- HTML templates are located in the `templates` directory.
- Static files, like CSS and JavaScript, support the user interface.

**Dependencies:**

- `Flask`: For the web interface.
- `db_utils`: For database operations.
- `json`, `os`, `re`: For handling JSON files, file paths, and tag processing.

---

### taginDB.py

This script is responsible for managing the initial setup and ongoing processing of the SQLite database. It ensures that image files and their metadata are correctly added to the system.

**Key Features:**

- **Database Initialization**:
  - Sets up tables for storing tags, images, and metadata.
  - Creates indices to improve query performance.
- **File Processing**:
  - Reads image files and their corresponding sidecar files.
  - Parses sidecar files for tags and associates them with the images.
- **Batch Processing**:
  - Handles large collections of images in manageable chunks.
  - Merges chunk databases into the main database to optimize efficiency.
- **Error Handling**:
  - Ensures robust processing by skipping problematic files and logging errors.

**Key Functions:**

- `initialize_database()`: Sets up the database schema, including tables and indices.
- `process_files_to_database()`: Processes images and sidecars in batches.
- `merge_chunk_databases()`: Combines temporary databases into the primary database.
- `cleanup_resources()`: Ensures that temporary files and resources are removed after processing.

**Dependencies:**

- `sqlite3`: For database operations.
- `os`, `shutil`: For file management and directory handling.
- `logging`: For error tracking and activity logging.
- `tqdm`: For displaying progress bars during batch processing.
- `psutil`: To optimize resource usage during multiprocessing.

---
