import os
import sqlite3
import subprocess
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

# Paths
script_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(script_dir, 'database', 'data.db')
dump_file = os.path.join(script_dir, 'database', 'dump.sql')
new_db_path = os.path.join(script_dir, 'database', 'new_data.db')

# Function to check database integrity
def check_database_integrity():
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA quick_check;")
        result = cursor.fetchone()
        conn.close()

        print("\n=== Database Integrity Check ===")
        if result and result[0] == "ok":
            print("Database integrity check passed: No corruption detected.")
            return True
        else:
            print("Database integrity check failed!")
            print("Issues reported:", result[0])
            return False
    except sqlite3.DatabaseError as e:
        print("Error during integrity check:", e)
        return False

# Function to check for corruption symptoms
def check_for_corruption():
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Attempt to read all rows from the `tags` table
        cursor.execute("SELECT id, image_path, tags FROM tags")
        rows = cursor.fetchall()
        
        print("\n=== Corruption Symptom Check ===")
        print(f"Read {len(rows)} rows successfully.")
        conn.close()
        return True
    except sqlite3.DatabaseError as e:
        print("Database error detected! Possible corruption:")
        print(e)
        return False
    except Exception as e:
        print("Unexpected error while checking for corruption:")
        print(e)
        return False

# Function to check for empty fields
def check_for_empty_fields():
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check for empty or NULL image paths
        cursor.execute("SELECT id, image_path, tags FROM tags WHERE image_path IS NULL OR image_path = ''")
        empty_image_path_entries = cursor.fetchall()
        if empty_image_path_entries:
            cursor.execute("DELETE FROM tags WHERE image_path IS NULL OR image_path = ''")
            print(f"Deleted {len(empty_image_path_entries)} entries with empty image paths.")
        
        # Check for empty or NULL tags
        cursor.execute("SELECT id, image_path, tags FROM tags WHERE tags IS NULL OR tags = ''")
        empty_tag_entries = cursor.fetchall()
        if empty_tag_entries:
            cursor.execute("DELETE FROM tags WHERE tags IS NULL OR tags = ''")
            print(f"Deleted {len(empty_tag_entries)} entries with empty tags.")
        
        conn.close()

        print("\n=== Empty Field Check ===")
        if not empty_image_path_entries and not empty_tag_entries:
            print("No empty fields found in the database.")
            return True
        else:
            if empty_image_path_entries:
                print("\nEntries with empty image paths were removed.")
            if empty_tag_entries:
                print("\nEntries with empty tags were removed.")
            return False
    except Exception as e:
        print("Error while checking for empty fields:", e)
        return False

def check_image_existence(entry):
    """Check if the image path exists for a single entry."""
    entry_id, image_path, tags = entry
    if not image_path or not os.path.exists(image_path):
        return entry_id
    return None

def check_and_remove_nonexistent_image_paths_threaded():
    try:
        print("\n=== Nonexistent Image Path Check and Cleanup ===")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Fetch all entries
        cursor.execute("SELECT id, image_path, tags FROM tags")
        entries = cursor.fetchall()
        conn.close()

        # Check for missing files using threading with tqdm
        nonexistent_entries = []
        with ThreadPoolExecutor(max_workers=1000) as executor:
            with tqdm(total=len(entries), desc="Checking files") as progress_bar:
                results = []
                for result in executor.map(check_image_existence, entries):
                    results.append(result)
                    progress_bar.update(1)
        nonexistent_entries = [entry_id for entry_id in results if entry_id is not None]

        # Remove entries with missing files
        if nonexistent_entries:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM tags WHERE id IN ({','.join(map(str, nonexistent_entries))})")
            conn.commit()
            conn.close()
            print(f"Deleted {len(nonexistent_entries)} entries with non-existent image paths.")

        
        if not nonexistent_entries:
            print("No entries with non-existent image paths found.")
            return True
        else:
            print("\nEntries with missing image paths were removed.")
            return False
    except Exception as e:
        print("Error while checking and removing entries with non-existent image paths:", e)
        return False

# Function to rebuild the database
def rebuild_database():
    try:
        print("\n=== Rebuilding Database ===")
        # Export the database to a dump file
        with open(dump_file, 'w') as f:
            conn = sqlite3.connect(db_path)
            for line in conn.iterdump():
                f.write(f"{line}\n")
            conn.close()
        print(f"Database dump created at: {dump_file}")

        # Rebuild the database from the dump file
        subprocess.run(["sqlite3", new_db_path, f".read {dump_file}"], check=True)
        print(f"Database successfully rebuilt at: {new_db_path}")
        return True
    except Exception as e:
        print("Failed to rebuild database:", e)
        return False

# Main execution
if __name__ == "__main__":
    if os.path.exists(db_path):
        print(f"Checking database for errors")
        
        # Step 1: Check database integrity
        integrity_ok = check_database_integrity()
        # Step 2: Check for corruption symptoms
        corruption_free = check_for_corruption()
        # Step 3: Check and remove entries with empty fields
        empties_ok = check_for_empty_fields()
        
        # Step 4: Check and remove entries with non-existent image paths
        nonexistent_paths_ok = check_and_remove_nonexistent_image_paths_threaded()
        # Step 4: Rebuild if necessary
        if not integrity_ok or not corruption_free:
            print("\nErrors detected in the database. Attempting to rebuild...")
            rebuild_success = rebuild_database()
            if rebuild_success:
                print("Rebuild successful. Verify the new database before use.")
            else:
                print("Rebuild failed. Manual intervention may be required.")
        if not empties_ok:
            print("\nEntries with Empty fields were removed. Please verify your database.")
            
        if not nonexistent_paths_ok:
            print("\nEntries with non-existent image paths were removed. Please verify your database.")
        elif nonexistent_paths_ok and integrity_ok and corruption_free and empties_ok:
            print("\nDatabase is healthy. No further action required.")
    else:
        print(f"Database not found at {db_path}. Please ensure the database exists and try again.")
