import sqlite3
import os
import re
from collections import defaultdict


# Define the database file path
db_file = './database/data.db'

# Ensure the database directory exists
os.makedirs(os.path.dirname(db_file), exist_ok=True)

# In-memory cache of search results: query -> list of matching image IDs.
# Cleared whenever tags, images or favorites change.
cached_queries = {}
MAX_CACHED_QUERIES = 200

# In-memory tag index: tag -> set of image IDs, built on the first search and
# kept up to date by upsert_tags() and delete_image().
_tag_index = None
_all_ids = None
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
    cached_queries.clear()


def build_tag_index():
    """(Re)build the in-memory tag index from the tags table."""
    global _tag_index, _all_ids
    index = defaultdict(set)
    all_ids = set()
    for image_id, tags_string in get_db_connection().execute('SELECT id, tags FROM tags'):
        all_ids.add(image_id)
        for tag in tags_string.split(', '):
            index[tag].add(image_id)
    _tag_index, _all_ids = index, all_ids


def _get_tag_index():
    if _tag_index is None:
        build_tag_index()
    return _tag_index


def _index_remove(image_id, tags):
    if _tag_index is None:
        return
    _all_ids.discard(image_id)
    for tag in tags:
        ids = _tag_index.get(tag)
        if ids is not None:
            ids.discard(image_id)
            if not ids:
                del _tag_index[tag]


def _index_add(image_id, tags):
    if _tag_index is None:
        return
    _all_ids.add(image_id)
    for tag in tags:
        _tag_index[tag].add(image_id)

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
    old_index_tags = result[0].split(', ') if result else []

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

    # Keep the search index in sync
    cursor.execute('SELECT id FROM tags WHERE image_path = ?', (image_path,))
    image_id = cursor.fetchone()[0]
    _index_remove(image_id, old_index_tags)
    _index_add(image_id, tags_string.split(', '))

    
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
        _index_remove(image_id, tags)

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


# Fetch metadata for many image IDs at once, preserving the order of image_ids
def fetch_metadata_by_ids(image_ids, chunk_size=900):
    """
    Batched version of fetch_metadata_by_id: one query per chunk of IDs instead of
    one query per image. IDs that no longer exist are skipped.
    chunk_size stays under SQLite's default limit on bound parameters.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    rows_by_id = {}
    for start in range(0, len(image_ids), chunk_size):
        chunk = image_ids[start:start + chunk_size]
        placeholders = ','.join('?' * len(chunk))
        cursor.execute(f'SELECT id, image_path, tags FROM tags WHERE id IN ({placeholders})', chunk)
        for row in cursor.fetchall():
            rows_by_id[row[0]] = {"id": row[0], "image_path": row[1], "tags": row[2].split(", ")}
    return [rows_by_id[i] for i in image_ids if i in rows_by_id]


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
    invalidate_stored_queries()
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
    invalidate_stored_queries()
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

def wildcard_to_regex(pattern):
    """Turn a tag pattern like "*door" or "blue_*" into a regex that must match
    the whole tag. Everything except * is matched literally."""
    return re.compile(".*".join(re.escape(part) for part in pattern.split("*")) + r"\Z")


def _ids_matching_tag(tag_or_pattern):
    """Image IDs having the given tag. A pattern with * matches any tag that fits it."""
    index = _get_tag_index()
    if "*" not in tag_or_pattern:
        return index.get(tag_or_pattern, set())
    regex = wildcard_to_regex(tag_or_pattern)
    matches = set()
    for tag, ids in index.items():
        if regex.match(tag):
            matches |= ids
    return matches


def _search_ids(search_query):
    """Return the sorted list of image IDs matching search_query, using the tag index."""
    # Split the search query into conditions
    search_tags = search_query.split(";")
    or_conditions = [term.split("|") for term in search_tags if "|" in term]
    exclude_conditions = [term[1:] for term in search_tags if term.startswith("-")]
    and_conditions = [
        term for term in search_tags if "|" not in term and not term.startswith("-")
    ]

    favorites_ids = set(fetch_favorite_image_ids())
    _get_tag_index()
    result = set(_all_ids)

    # user:favorites as an AND term limits results to favorites;
    # as an exclude term it removes them.
    if "user:favorites" in and_conditions:
        and_conditions.remove("user:favorites")
        result &= favorites_ids
    elif "user:favorites" in exclude_conditions:
        exclude_conditions.remove("user:favorites")
        result -= favorites_ids

    # AND: every term must match (supports * wildcards)
    for condition in and_conditions:
        result &= _ids_matching_tag(condition)
        if not result:
            return []

    # OR groups: at least one group must match (exact tags or user:favorites)
    if or_conditions:
        or_match = set()
        for or_group in or_conditions:
            for tag in or_group:
                or_match |= favorites_ids if tag == "user:favorites" else _get_tag_index().get(tag, set())
        result &= or_match

    # NOT: drop images with any excluded tag
    for exclude_tag in exclude_conditions:
        result -= _get_tag_index().get(exclude_tag, set())

    return sorted(result)


def search_images_with_conditions(search_query, onlyids=False):
    """
    Searches for images based on AND (;), OR (|), and NOT (-) conditions,
    with * wildcards in AND terms and support for "user:favorites".
    Results are cached in memory until tags, images or favorites change.

    Args:
        search_query (str): A string of search tags.
        onlyids (bool): Return only the matching image IDs.

    Returns:
        list: A list of dictionaries containing image metadata, or image IDs.
    """
    image_ids = cached_queries.get(search_query)
    if image_ids is None:
        image_ids = _search_ids(search_query)
        if len(cached_queries) >= MAX_CACHED_QUERIES:
            cached_queries.pop(next(iter(cached_queries)))  # drop the oldest entry
        cached_queries[search_query] = image_ids

    if onlyids:
        return image_ids
    return fetch_metadata_by_ids(image_ids)
