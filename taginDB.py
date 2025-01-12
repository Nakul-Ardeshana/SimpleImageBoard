import os
import sqlite3
import logging
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import psutil
import atexit
import shutil

# Directory paths
script_dir = os.path.dirname(os.path.abspath(__file__))
directory_path = os.path.join(script_dir, 'static', 'images')
chunking_path = os.path.join(script_dir, 'database', 'chunks')
db_path = os.path.join(script_dir, 'database', 'data.db')
log_file_path = os.path.join(script_dir, 'logs', 'prepping_database_log.txt')

# Ensure necessary directories exist
os.makedirs(os.path.dirname(db_path), exist_ok=True)
os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

# Configure logging
logging.basicConfig(filename=log_file_path, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Clean up resources
def cleanup_resources():
    """Clean up resources on exit."""
atexit.register(cleanup_resources)

# Initialize the main database
def initialize_database():
    """Initialize the SQLite database with required tables."""
    conn = sqlite3.connect(db_path)
    conn.execute('''
    CREATE TABLE IF NOT EXISTS tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        image_path TEXT UNIQUE,
        tags TEXT
    )''')
    
    
    cursor = conn.cursor()
    # Create index for id
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS favorites (
        id INTEGER PRIMARY KEY,
        image_id INTEGER UNIQUE
    )
    ''')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_id ON tags (id);")
    # Create index for image_path
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_image_path ON tags (image_path);")
    # Create index for tags
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tags ON tags (tags);")
    conn.commit()
    conn.close()

def delete_chunk_directory(chunking_path):
    """
    Delete the chunk directory and its contents after merging all data into the master database.

    Args:
        chunking_path (str): The path to the chunk directory to be deleted.
    """
    if os.path.exists(chunking_path):
        try:
            shutil.rmtree(chunking_path)
            logging.info(f"Chunk directory '{chunking_path}' successfully deleted.")
        except Exception as e:
            logging.error(f"Failed to delete chunk directory '{chunking_path}': {e}")
    else:
        logging.warning(f"Chunk directory '{chunking_path}' does not exist.")

# Retrieve existing files
def get_existing_files():
    """Retrieve the list of already processed files from the database."""
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT image_path FROM tags")
        return {row[0] for row in cursor.fetchall()}
    finally:
        conn.close()

# Get files to process
def get_files_to_process(directory, existing_files):
    """Retrieve files to process and count total sidecars."""
    files_to_process = []
    total_sidecars = 0
    for root, _, files in os.walk(directory):
        images = {os.path.splitext(f)[0]: f for f in files if f.lower().endswith(('.jpg', '.png', '.mp4', '.webm', '.gif', '.bmp'))}
        sidecars = {os.path.splitext(f)[0]: f for f in files if f.lower().endswith('.txt')}
        total_sidecars += len(sidecars)
        for name in sidecars:
            if name in images:
                image_path = os.path.relpath(os.path.join(root, images[name]), script_dir).replace("\\", "/")
                if image_path not in existing_files:
                    sidecar_path = os.path.join(root, sidecars[name])
                    files_to_process.append((image_path, sidecar_path))
    return files_to_process, total_sidecars

# Calculate batch size
def calculate_batch_size(total_files, min_files_per_chunk=2000, max_chunks=50):
    """Calculate a balanced batch size to avoid too many or too few chunks."""
    if total_files < min_files_per_chunk:
        min_files_per_chunk = total_files
    max_files_per_chunk = max(1, total_files // max_chunks)
    batch_size = max(min_files_per_chunk, min(max_files_per_chunk, total_files))
    logging.info(f"Calculated batch size: {batch_size}")
    return batch_size

# Read sidecar file
def read_sidecar_file(sidecar_path):
    """Read and parse the sidecar file for tags."""
    try:
        with open(sidecar_path, 'r', encoding='utf-8') as f:
            tags = [tag.replace(" ", "_").strip() for tag in f.read().strip().splitlines() if tag]
    except UnicodeDecodeError:
        with open(sidecar_path, 'r', encoding='latin-1') as f:
            tags = [tag.replace(" ", "_").strip() for tag in f.read().strip().splitlines() if tag]
    except Exception as e:
        logging.error(f"Error reading {sidecar_path}: {e}")
        tags = []
    return tags.remove("user:favorites")

def process_single_file(args):
    """Process a single file and return the parsed tags."""
    image_path, sidecar_path = args
    tags = read_sidecar_file(sidecar_path)
    return image_path, ', '.join(tags)

def process_files_chunk(chunk):
    """Process a chunk of files using ThreadPoolExecutor."""
    max_workers = min(60, int(psutil.cpu_count(logical=True)* 4))
    logging.info(f"Using {max_workers} workers for file-level processing")

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_single_file, (image_path, sidecar_path)): (image_path, sidecar_path) for image_path, sidecar_path in chunk}
        for future in futures:
            try:
                results.append(future.result())
            except Exception as e:
                logging.error(f"Error processing file {futures[future]}: {e}")
    
    return results

def process_chunk(chunk, chunk_index, chunking_path):
    """Process a single chunk and save to a chunk database in smaller batches."""
    chunk_db_path = os.path.join(chunking_path, f"chunk_{chunk_index}.db")
    os.makedirs(os.path.dirname(chunk_db_path), exist_ok=True)
    conn = sqlite3.connect(chunk_db_path)
    try:
        # Create table if it doesn't exist
        conn.execute('''
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_path TEXT UNIQUE,
            tags TEXT
        )''')
        conn.commit()

        # Process files in the chunk and insert in smaller batches
        records = process_files_chunk(chunk)
        conn.executemany('''
        INSERT INTO tags (image_path, tags)
        VALUES (?, ?)
        ON CONFLICT(image_path) DO UPDATE SET tags = excluded.tags
        ''', records)
        conn.commit()
    except Exception as e:
        logging.error(f"Error processing chunk {chunk_index}: {e}")
    finally:
        conn.close()


# Process files into chunk databases
def process_files(files_to_process, batch_size, chunking_path):
    """Process all new files in the specified directory into chunk databases using ProcessPoolExecutor."""
    chunks = [files_to_process[i:i + batch_size] for i in range(0, len(files_to_process), batch_size)]
    total_chunks = len(chunks)

    # Use a progress bar in the main thread
    with tqdm(total=total_chunks, desc=f"Processing chunks ({batch_size} files each)", dynamic_ncols=True) as progress_bar:
        with ProcessPoolExecutor(max_workers=int(psutil.cpu_count(logical=True)/2)) as executor:
            futures = []
            for chunk_index, chunk in enumerate(chunks):
                futures.append(executor.submit(process_chunk, chunk, chunk_index, chunking_path))

            # Monitor progress as futures complete
            for future in futures:
                future.result()  # Wait for each process to complete
                progress_bar.update(1)  # Update progress bar in the main thread

    return total_chunks

# Merge chunk databases
def merge_chunk_databases(directory, master_db_path, num_chunks, batch_size=1000):
    """
    Merge all chunk databases into a single master database efficiently with a progress bar.
    
    Parameters:
        directory (str): Directory containing the chunk databases.
        master_db_path (str): Path to the master database.
        num_chunks (int): Number of chunk databases to merge.
        batch_size (int): Number of rows to insert per transaction.
    """
    conn_master = sqlite3.connect(master_db_path)
    try:
        # Ensure the master database has the required table
        conn_master.execute('''
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_path TEXT UNIQUE,
            tags TEXT
        )''')
        conn_master.commit()

        with tqdm(total=num_chunks, desc="Merging chunks", unit="chunk", dynamic_ncols=True) as progress_bar:
            for chunk_index in range(num_chunks):
                chunk_db_path = os.path.join(directory, f"chunk_{chunk_index}.db")
                conn_chunk = sqlite3.connect(chunk_db_path)
                try:
                    cursor = conn_chunk.cursor()
                    cursor.execute("SELECT image_path, tags FROM tags")

                    # Fetch rows in batches for efficient insertion
                    while True:
                        rows = cursor.fetchmany(batch_size)
                        if not rows:
                            break

                        conn_master.executemany('''
                        INSERT INTO tags (image_path, tags)
                        VALUES (?, ?)
                        ON CONFLICT(image_path) DO UPDATE SET tags = excluded.tags
                        ''', rows)

                    conn_master.commit()  # Commit once per chunk for efficiency
                finally:
                    conn_chunk.close()
                    os.remove(chunk_db_path)  # Clean up chunk database
                
                progress_bar.update(1)  # Update progress bar after each chunk
    finally:
        conn_master.close()
# Main execution block
if __name__ == '__main__':
    logging.info("Initializing database and resources...")
    print("Initializing database and resources...")
    initialize_database()
    
    logging.info("Fetching existing entries from the database...")
    print("Fetching existing entries from the database...")
    existing_files = get_existing_files()
    
    logging.info("Identifying files that still need to be processed...")
    print("Identifying files that still need to be processed...")
    files_to_process, total_sidecars = get_files_to_process(directory_path, existing_files)

    print(f"Total sidecar files: {total_sidecars}")
    print(f"Already processed files: {len(existing_files)}")
    print(f"New files to process: {len(files_to_process)}")
    logging.info(f"Total sidecar files found: {total_sidecars}")
    logging.info(f"New files to process: {len(files_to_process)}")

    if not files_to_process:
        print("No new files to process. Exiting.")
        exit()
    user_input = input("Do you want to proceed with processing the new files? (y/n): ").strip().lower()
    if user_input != 'y':
        print("Exiting the program. No files were processed.")
        exit()

    batch_size = calculate_batch_size(len(files_to_process))
    try:
        num_chunks = process_files(files_to_process, batch_size, chunking_path)
        
        print("Starting to merge chunk databases...")
        merge_chunk_databases(chunking_path, db_path, num_chunks, batch_size)
    finally:
        # Delete the chunk directory after successful merge
        delete_chunk_directory(chunking_path)
    print(f"All chunks merged into master database at {db_path}")
