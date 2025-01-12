import sqlite3
import os
import re
import json


# Define the database file path
db_file = './database/data.db'
# Define the path for the JSON cache file
CACHE_FILE = './database/cached_queries.json'

# Ensure the database directory exists
os.makedirs(os.path.dirname(db_file), exist_ok=True)
with open(CACHE_FILE, 'w') as f:
    json.dump({}, f)
    
cached_queries = {}
_connection = sqlite3.connect(db_file, check_same_thread=False)
_connection.execute(f"PRAGMA max_variable_number = 30000")

def get_db_connection():
    global _connection
    return _connection

def initialize_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        image_path TEXT UNIQUE,
        tags TEXT
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tag_counts (
        tag TEXT PRIMARY KEY,
        count INTEGER DEFAULT 0
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS favorites (
        id INTEGER PRIMARY KEY,
        image_id INTEGER UNIQUE
    )
    ''')
    conn.commit()

def invalidate_stored_queries():
    global cached_queries
    cached_queries = {}
    with open(CACHE_FILE, 'w') as f:
        json.dump({}, f)

# Fetch tags and ID for a specific image
def fetch_tags_with_id(image_path):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, tags FROM tags WHERE image_path = ?', (image_path,))
    result = cursor.fetchone()
    if result:
        return {"id": result[0], "tags": result[1].split(', ')}
    return {"id": None, "tags": []}

# Fetch all image paths and IDs from the database
def fetch_all_images_with_ids():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, image_path, tags FROM tags')
    result = cursor.fetchall()
    return [{"id": row[0], "image_path": row[1], "tags":row[2].split(",")} for row in result]

# Fetch all image paths and IDs from the database
def fetch_all_images_with_idsfr():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM tags')
    result = cursor.fetchall()
    return [{"id": row[0]} for row in result]

# Insert or update tags for a specific imae
def upsert_tags(image_path, new_tags):
    invalidate_stored_queries()
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch current tags for the image
    cursor.execute('SELECT tags FROM tags WHERE image_path = ?', (image_path,))
    result = cursor.fetchone()
    old_tags = set(result[0].split(', ')) if result else set()

    # Calculate tag differences
    new_tags_set = set(new_tags)
    added_tags = new_tags_set - old_tags
    removed_tags = old_tags - new_tags_set

    # Update tag counts
    for tag in added_tags:
        cursor.execute('INSERT INTO tag_counts (tag, count) VALUES (?, 1) ON CONFLICT(tag) DO UPDATE SET count = count + 1', (tag,))
    for tag in removed_tags:
        cursor.execute('UPDATE tag_counts SET count = count - 1 WHERE tag = ?', (tag,))

    # Update tags table
    tags_string = ', '.join(new_tags)
    cursor.execute('''
        INSERT INTO tags (image_path, tags)
        VALUES (?, ?)
        ON CONFLICT(image_path)
        DO UPDATE SET tags = excluded.tags
    ''', (image_path, tags_string))
    conn.commit()

    
# Delete a specific image from the database
def delete_image(image_path):
    invalidate_stored_queries()
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch tags associated with the image
    cursor.execute('SELECT id, tags FROM tags WHERE image_path = ?', (image_path,))
    result = cursor.fetchone()
    if result:
        image_id, tags = result[0], result[1].split(', ')
        # Check if the image is a favorite and remove it from favorites
        cursor.execute('SELECT COUNT(*) FROM favorites WHERE image_id = ?', (image_id,))
        is_favorited = cursor.fetchone()[0] > 0
        if is_favorited:
            remove_from_favorites(image_id)
        
        for tag in tags:
            cursor.execute('UPDATE tag_counts SET count = count - 1 WHERE tag = ?', (tag,))

    # Delete the image record
    cursor.execute('DELETE FROM tags WHERE image_path = ?', (image_path,))
    conn.commit()

    # Delete the actual file if it exists
    if os.path.exists(image_path):
        os.remove(image_path)

    # Delete the corresponding .txt file if it exists
    txt_file_path = os.path.splitext(image_path)[0] + ".txt"
    if os.path.exists(txt_file_path):
        os.remove(txt_file_path)

# Fetch the image path using the ID
def fetch_image_path_by_id(image_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT image_path FROM tags WHERE id = ?', (image_id,))
    result = cursor.fetchone()
    
    return result[0] if result else None

# Update tags using the image ID
def update_tags_by_id(image_id, tags):
    image_path = fetch_image_path_by_id(image_id)
    if image_path:
        upsert_tags(image_path, tags)
        invalidate_stored_queries()
        return True
    return False

# Delete an image using the image ID
def delete_image_by_id(image_id):
    image_path = fetch_image_path_by_id(image_id)
    if image_path:
        delete_image(image_path)
        invalidate_stored_queries()
        return True
    return False

# Fetch all unique tags in the database
def fetch_all_tags():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT tags FROM tags')
    all_tags = [tag for row in cursor.fetchall() for tag in row[0].split(', ')]
    
    return list(set(all_tags))  # Return unique tags

# Fetch image metadata by ID
def fetch_metadata_by_id(image_id):
    """
    Fetches metadata (image path and tags) for a given image ID.

    Args:
        image_id (int): The ID of the image in the database.

    Returns:
        dict: A dictionary containing 'image_path' and 'tags', or None if not found.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, image_path, tags FROM tags WHERE id = ?', (image_id,))
    result = cursor.fetchone()    
    if result:
        return {"id": result[0], "image_path": result[1], "tags": result[2].split(", ")}
    return None


# Fetch the count for a specific tag
def fetch_tag_count(tag):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT count FROM tag_counts WHERE tag = ?', (tag,))
    result = cursor.fetchone()
    
    return result[0] if result else 0


# Fetch all tags and their counts
def fetch_all_tag_counts():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT tag, count FROM tag_counts')
    results = cursor.fetchall()
    
    return {row[0]: row[1] for row in results}

# Delete a tag from the database
def delete_tag_count(tag):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM tag_counts WHERE tag = ?', (tag,))
    conn.commit()
    

# Add an image to favorites
def add_to_favorites(image_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO favorites (image_id) VALUES (?)', (image_id,))
    # Get the count of entries in the favorites table
    cursor.execute('SELECT COUNT(*) FROM favorites')
    new_count = cursor.fetchone()[0]
    cursor.execute('''
        UPDATE tag_counts
        SET count = ?
        WHERE tag = 'user:favorites'
        ''', (new_count,))
    conn.commit()
    

# Remove an image from favorites
def remove_from_favorites(image_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM favorites WHERE image_id = ?', (image_id,))
    cursor.execute('SELECT COUNT(*) FROM favorites')
    new_count = cursor.fetchone()[0]
    cursor.execute('''
        UPDATE tag_counts
        SET count = ?
        WHERE tag = 'user:favorites'
        ''', (new_count,))
    conn.commit()
    

# Fetch all favorite image IDs
def fetch_favorite_image_ids():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT image_id FROM favorites')
    results = cursor.fetchall()
    
    return [row[0] for row in results]

def fetch_cached_query_from_json(query, cached_queries):
    """
    Fetches cached results for a query from the JSON file.

    Args:
        query (str): The search query.

    Returns:
        list: A list of image IDs if the query is cached, or None if not found.
    """
    return cached_queries, cached_queries.get(query, None)

def save_query_to_json(query, image_ids, cached_queries):
    """
    Saves a query and its results to the JSON cache file.

    Args:
        query (str): The search query.
        image_ids (list): The list of matching image IDs.
    """
    cached_queries[query] = image_ids
    with open(CACHE_FILE, 'w') as f:
        json.dump(cached_queries, f, indent=4)
    return cached_queries

def search_images_with_conditions(search_query, onlyids=False):
    global cached_queries
    """
    Searches the database for images based on AND, OR, and NOT conditions,
    utilizing a JSON file for caching results. Supports "user:favorites".

    Args:
        search_query (str): A string of search tags.

    Returns:
        list: A list of dictionaries containing image metadata or image IDs.
    """

    # Check if the query is cached in the JSON file
    cached_queries, cached_image_ids = fetch_cached_query_from_json(search_query, cached_queries)
    result_images = []
    if cached_image_ids and onlyids:
        return cached_image_ids
    if cached_image_ids:
        for imgID in cached_image_ids:
            # Fetch metadata for cached image IDs in batches
            result_images.append(fetch_metadata_by_id(imgID))
        return result_images

    # Parse the search query
    conn = get_db_connection()
    cursor = conn.cursor()

    # Split the search query into conditions
    search_tags = search_query.split(";")
    or_conditions = [term.split("|") for term in search_tags if "|" in term]
    exclude_conditions = [term[1:] for term in search_tags if term.startswith("-")]
    and_conditions = [
        term for term in search_tags if "|" not in term and not term.startswith("-")
    ]

    # Handle user:favorites logic
    favorites_ids = set(fetch_favorite_image_ids())
    favorites_excluded = False
    all_images = []
    # Process user:favorites in different conditions
    if "user:favorites" in and_conditions:
        and_conditions.remove("user:favorites")
        if favorites_ids:  # Ensure there are favorite IDs to fetch
            placeholders = ','.join(['?'] * len(favorites_ids))
            cursor.execute(f"SELECT id, image_path, tags FROM tags WHERE id IN ({placeholders})", tuple(favorites_ids))
            all_images = cursor.fetchall()

    elif "user:favorites" in exclude_conditions:
        favorites_excluded = True
        exclude_conditions.remove("user:favorites")
        cursor.execute("SELECT id, image_path, tags FROM tags")
        all_images = cursor.fetchall()
    else:
        cursor.execute("SELECT id, image_path, tags FROM tags")
        all_images = cursor.fetchall()

    result_images = []
    for image_id, image_path, tags_string in all_images:
        tags = tags_string.split(", ")

        # Apply AND conditions
        matches_all_and_conditions = True
        for condition in and_conditions:
            if "*" in condition:
                # Handle wildcard matching
                pattern = re.compile(condition.replace("*", ".*"))
                if not any(pattern.match(tag) for tag in tags):
                    matches_all_and_conditions = False
                    break
            else:
                # Exact match
                if condition not in tags:
                    matches_all_and_conditions = False
                    break

        # Skip this image if AND conditions are not met
        if not matches_all_and_conditions:
            continue

        # Apply OR conditions
        if or_conditions:
            or_match = False
            for or_group in or_conditions:
                if "user:favorites" in or_group:
                    or_group_tags = set(or_group) - {"user:favorites"}
                    if image_id in favorites_ids or any(tag in tags for tag in or_group_tags):
                        or_match = True
                        break
                elif any(tag in tags for tag in or_group):
                    or_match = True
                    break
            if not or_match:
                continue

        # Apply NOT conditions
        if any(exclude_tag in tags for exclude_tag in exclude_conditions):
            continue

        # Exclude favorites if specified
        if favorites_excluded and image_id in favorites_ids:
            continue

        # Include the image if all conditions are satisfied
        result_images.append({
            "id": image_id,
            "image_path": image_path,
            "tags": tags
        })

    # Cache the query results in JSON
    image_ids = [image["id"] for image in result_images]
    cached_queries = save_query_to_json(search_query, image_ids, cached_queries)
    if onlyids:
        return image_ids
    return result_images


