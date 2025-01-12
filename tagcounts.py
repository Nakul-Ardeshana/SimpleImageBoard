import sqlite3
from collections import Counter
import os
import re
from concurrent.futures import ThreadPoolExecutor

def process_batch(rows, tag_splitter):
    """Process a batch of rows and return tag counts as a Counter."""
    local_counter = Counter()
    for row in rows:
        tag_list = tag_splitter.split(row[0])  # Split tags using regex
        local_counter.update(tag_list)  # Update the Counter
    return local_counter

def count_tags_in_large_db(db_file, batch_size=1000, num_threads=4):
    # Connect to the SQLite database
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Initialize a regex pattern for splitting tags
    tag_splitter = re.compile(r'\s*,\s*')  # Split by comma, trims whitespace

    try:
        # Create the tag_counts table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tag_counts (
            tag TEXT PRIMARY KEY,
            count INTEGER
        )
        ''')

        # Clear existing data in the tag_counts table
        cursor.execute('DELETE FROM tag_counts')

        # Initialize a Counter to accumulate tag counts
        global_tag_counts = Counter()

        # Fetch tags in batches
        cursor.execute('SELECT tags FROM tags WHERE tags IS NOT NULL AND tags != ""')

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            while True:
                rows = cursor.fetchmany(batch_size)  # Fetch a batch of rows
                if not rows:  # Break the loop if no more rows
                    break
                # Submit the batch for parallel processing
                futures.append(executor.submit(process_batch, rows, tag_splitter))

            # Collect results from all futures
            for future in futures:
                global_tag_counts.update(future.result())

        # Bulk insert the tag counts into the database
        cursor.executemany(
            'INSERT INTO tag_counts (tag, count) VALUES (?, ?)',
            global_tag_counts.most_common()
        )
        
        # Get the count of entries in the favorites table
        cursor.execute('SELECT COUNT(*) FROM favorites')
        favorites_count = cursor.fetchone()[0]

        # Add the user:favorites tag with the retrieved count
        cursor.execute('INSERT INTO tag_counts (tag, count) VALUES (?, ?)', ('user:favorites', favorites_count))

        # Commit changes
        conn.commit()
        print(f"Tag counts saved to the 'tag_counts' table in {db_file}")
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        # Close the connection
        conn.close()

# Define path to the database
script_dir = os.path.dirname(os.path.abspath(__file__))
db_file = os.path.join(script_dir, 'database', 'data.db')

# Generate the tag counts in the same database
count_tags_in_large_db(db_file, batch_size=1000, num_threads=8)
