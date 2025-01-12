port = 5000
from flask import Flask, render_template, request, jsonify, redirect
import os
import logging
import json
import re
import time
from collections import defaultdict
from db_utils import *


# Prompt the user for execution mode
print("Choose the mode to run the server:")
print("1. Localhost only (127.0.0.1)")
print("2. Localhost + Network (accessible by other devices on the same network)")
mode = input("Enter 1 or 2: ").strip()
if mode == "1":
    host = "127.0.0.1"  # Localhost
    print(f"\nRunning in localhost mode.\n * Access the server at http://127.0.0.1:{port}/")
elif mode == "2":
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    host = "0.0.0.0"  # Allow network access
    print(f"\nRunning in network mode.\n * Access the server locally at http://127.0.0.1:{port}/\n * Access the server on the network at http://{local_ip}:{port}/")
else:
    print("\nInvalid choice. Defaulting to localhost mode.")
    print(f"\nRunning in localhost mode.\n * Access the server at http://127.0.0.1:{port}/")
    host = "127.0.0.1"
time.sleep(2)

images_per_page = 30

# Define the custom order
colororder = [7, 1, 4, 3, 5, 0, 2]

app = Flask(__name__)
log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

favorite_ids = []
color_dict = {}

with open("./templates/list of tags.json", "r") as json_file:
    data = json.load(json_file)
    color_dict = data


def colorcode(tag):
    try:
        color = int(color_dict[tag]["type"])
    except:
        color = 0
    return color

def analyze_cooccurrence(search_results):
    """
    Analyze tag co-occurrence within search results to find related tags.

    Args:
        search_results (list): List of image identifiers matching the search.

    Returns:
        list: Sorted list of related tags based on co-occurrence frequency.
    """
    cooccurrence_counts = defaultdict(int)

    for image_data in search_results:
        tags = image_data["tags"]
        for tag in tags:
            cooccurrence_counts[tag] += 1

    # Sort tags by co-occurrence count in descending order
    sorted_related_tags = sorted(cooccurrence_counts.items(), key=lambda x: x[1], reverse=True)

    # Return only the tags, not the counts
    return [tag for tag, count in sorted_related_tags]

def process_edit_tags(filename, updated_tags):
    """
    Processes and updates tags for a specific image file using the upsert_tags function.
    Args:
        filename (str): The file path of the image.
        updated_tags (list): The updated list of tags.
    """
    updated_tags = list(dict.fromkeys(updated_tags))  # Remove duplicates
    upsert_tags(filename, updated_tags)  # Use the centralized logic

    # Update the sidecar file (.txt) associated with the filename
    txt_file = "./" + filename.replace(os.path.splitext(os.path.basename(filename))[1], ".txt")
    if os.path.exists(txt_file):
        with open("./" + txt_file, "w") as f:
            for tag in updated_tags:
                f.write(tag.replace("_", " ") + "\n")

app = Flask(__name__)

@app.route("/autocomplete")
def autocomplete():
    query = request.args.get("q", "").strip().lower()
    if not query:
        return jsonify([])

    # Fetch all tags and their counts
    all_tag_counts = fetch_all_tag_counts()

    # Handle OR (`|`) by using only the last term for autocomplete
    or_parts = query.split("|")
    current_query = or_parts[-1]  # Only consider the last part for suggestions

    # Determine if it is an "exclude" query (starts with `-`)
    is_exclude = current_query.startswith("-")
    if is_exclude:
        current_query = current_query[1:]  # Remove `-` for matching purposes

    # Filter tags based on the query
    if "*" in current_query:
        pattern = re.compile("^" + ".*".join(re.escape(part) for part in current_query.split("*")))
        suggestions = [
            {"tag": tag, "count": count, "type": colorcode(tag)}
            for tag, count in all_tag_counts.items()
            if pattern.match(tag.lower())
        ]
    else:
        suggestions = [
            {"tag": tag, "count": count, "type": colorcode(tag)}
            for tag, count in all_tag_counts.items()
            if tag.lower().startswith(current_query)
        ]

    # If it is an exclude query, add `-` to the beginning of each suggestion
    if is_exclude:
        for suggestion in suggestions:
            suggestion["tag"] = f"-{suggestion['tag']}"
    
    user_favorites = next((s for s in suggestions if s["tag"] == "user:favorites"), None)
    if user_favorites:
        suggestions = [user_favorites] + [s for s in suggestions if s["tag"] != "user:favorites"]

    # Limit the suggestions to 10
    return jsonify(suggestions[:10])

@app.route("/")
@app.route("/index")
def index():
    return render_template("search.html", pagetype = "index")

@app.route("/allofthem/<int:page>")
@app.route("/allofthem/")
@app.route("/allofthem")
def allofthem(page=1):
    # Perform the search using the database
    start_index = (page - 1) * images_per_page
    end_index = start_index + images_per_page
    search_results = fetch_all_images_with_ids()
    search_results = [item for item in search_results if item is not None]
    total_images = len(search_results)

    image_data = []
    images_processed =0

    # Process search results
    for i, result in enumerate(search_results):
        # Only process results within the requested page range
        if start_index <= i < end_index:
            if os.path.exists("./" + result['image_path'].replace('\\', '/')):
                file_extension = os.path.splitext(os.path.basename(result["image_path"]))[1].lower()
                media_type = "image" if file_extension in [".jpg", ".jpeg", ".png", ".gif"] else "video"

                image_data.append({
                    "image_path": "/" + result['image_path'].replace('\\', '/'),
                    "tags": result["tags"],
                    "name": os.path.splitext(os.path.basename(result["image_path"]))[0],
                    "mediatype": media_type,
                    "ID": result["id"]
                })
                images_processed +=1
            else:
                # Referrer check
                referrer = request.referrer if "request" in globals() else None
                is_from_result_page = False
                referrer_id = None

                if referrer:
                    referrer_path = referrer.split(request.host_url)[-1]
                    if referrer_path.startswith("result/"):
                        referrer_parts = referrer_path.split("/")
                        if len(referrer_parts) > 1:
                            referrer_id = referrer_parts[1]
                            is_from_result_page = True

                # Only delete if not from corresponding result/<id> page
                if not (is_from_result_page and referrer_id == str(result['id'])):
                    print(f"Image does not exist: {result['image_path']}, deleting entry...")
                    delete_image_by_id(result['id'])
                    
        if images_processed == images_per_page:
            break
    # Pagination logic
    paginated_images = image_data    
    
    # Collect unique tags from the images on the current page
    unique_tags = analyze_cooccurrence(paginated_images)
    # Select up to 20 unique tags from the current page
    unique_tags = list(unique_tags)[:35]
    tag_list = []
    for tag in unique_tags:
        tag_list.append([tag,fetch_tag_count(tag.strip()),colorcode(tag.strip())])
    
    tag_list = sorted(tag_list, key=lambda x: (colororder.index(x[2]), -x[1], x[0]))
    
    # Total pages
    total_pages = (total_images + images_per_page - 1) // images_per_page  # Ceiling division


    return render_template("index.html", image_data=paginated_images, page=page, total_pages=total_pages, unique_tags=tag_list,total_images=total_images,context="allofthem", pagetype = "gallery")

@app.route("/search/<searchTags>/")
@app.route("/search/<searchTags>")
@app.route("/search/<searchTags>/<int:page>")
def search(searchTags, page=1):
    # Perform the search using the database
    start_index = (page - 1) * images_per_page
    end_index = start_index + images_per_page
    search_results = search_images_with_conditions(searchTags, onlyids=False)
    search_results = [item for item in search_results if item is not None]
    total_images = len(search_results)

    image_data = []
    images_processed =0

    # Process search results
    for i, result in enumerate(search_results):
        # Only process results within the requested page range
        if start_index <= i < end_index:
            if os.path.exists("./" + result['image_path'].replace('\\', '/')):
                file_extension = os.path.splitext(os.path.basename(result["image_path"]))[1].lower()
                media_type = "image" if file_extension in [".jpg", ".jpeg", ".png", ".gif"] else "video"

                image_data.append({
                    "image_path": "/" + result['image_path'].replace('\\', '/'),
                    "tags": result["tags"],
                    "name": os.path.splitext(os.path.basename(result["image_path"]))[0],
                    "mediatype": media_type,
                    "ID": result["id"]
                })
                images_processed +=1
            else:
                # Referrer check
                referrer = request.referrer if "request" in globals() else None
                is_from_result_page = False
                referrer_id = None

                if referrer:
                    referrer_path = referrer.split(request.host_url)[-1]
                    if referrer_path.startswith("result/"):
                        referrer_parts = referrer_path.split("/")
                        if len(referrer_parts) > 1:
                            referrer_id = referrer_parts[1]
                            is_from_result_page = True

                # Only delete if not from corresponding result/<id> page
                if not (is_from_result_page and referrer_id == str(result['id'])):
                    print(f"Image does not exist: {result['image_path']}, deleting entry...")
                    delete_image_by_id(result['id'])
                    
        if images_processed == images_per_page:
            break
    # Pagination logic
    paginated_images = image_data

    # Total pages for pagination
    total_pages = (total_images + images_per_page - 1) // images_per_page  # Ceiling division

    # Collect unique tags from the images on the current page
    unique_tags = analyze_cooccurrence(paginated_images)
    # Select up to 20 unique tags from the current page
    unique_tags = list(unique_tags)[:35]
    tag_list = []
    for tag in unique_tags:
        tag_list.append([tag,fetch_tag_count(tag.strip()),colorcode(tag.strip())]) 

    tag_list = sorted(tag_list, key=lambda x: (colororder.index(x[2]), -x[1], x[0]))

    # Render the results in index.html with pagination
    return render_template(
        "index.html",
        image_data=paginated_images,
        page=page,
        total_pages=total_pages,
        query=searchTags,  # Pass search tags for URL construction
        unique_tags=tag_list,
        total_images=total_images,
        context="search",
        pagetype = "gallery"
    )

@app.route("/favorites/<int:page>")
@app.route("/favorites/")
@app.route("/favorites")
def favorites(page=1):
    # Fetch favorite image IDs from the database
    favorite_ids = fetch_favorite_image_ids()
    favorite_ids = [item for item in favorite_ids if item is not None]

    # Fetch metadata for each favorite image
    image_data = []
    for image_id in favorite_ids:
        metadata = fetch_metadata_by_id(image_id)
        if not metadata:
            continue  # Skip if metadata is not found

        image_path = metadata["image_path"]
        tags = metadata["tags"]

        # Ensure the file exists in the directory
        if not os.path.exists(image_path):
            continue  # Skip if the file does not exist

        # Convert the path to a format accessible by Flask
        image_url = image_path.replace("\\", "/")

        # Determine media type
        file_extension = os.path.splitext(os.path.basename(image_path))[1].lower()
        media_type = "image" if file_extension in [".jpg", ".jpeg", ".png", ".gif"] else "video"

        # Append metadata to image_data
        image_data.append(
            {
                "image_path": image_url,  # Make it a root path
                "tags": tags,
                "name": os.path.splitext(os.path.basename(image_path))[0],
                "mediatype": media_type,
                "ID": image_id
            }
        )

    # Pagination logic
    total_images = len(image_data)
    images_per_page = 10  # Define how many images per page
    start_index = (page - 1) * images_per_page
    end_index = start_index + images_per_page
    paginated_images = image_data[start_index:end_index]

    # Collect unique tags from the images on the current page
    unique_tags = analyze_cooccurrence(paginated_images)
    unique_tags = list(unique_tags)[:35]
    tag_list = []
    for tag in unique_tags:
        tag_list.append([tag, fetch_tag_count(tag.strip()), colorcode(tag.strip())])

    tag_list = sorted(tag_list, key=lambda x: (colororder.index(x[2]), -x[1], x[0]))

    # Total pages
    total_pages = (total_images + images_per_page - 1) // images_per_page  # Ceiling division

    return render_template(
        "index.html",
        image_data=paginated_images,
        page=page,
        total_pages=total_pages,
        unique_tags=tag_list,
        total_images=total_images,
        context="favorites",
        pagetype = "gallery"
    )

@app.route("/result/<id>")
@app.route("/result/<id>/")
def result(id):
    # Convert id to integer for database queries
    tag_list=[]
    try:
        id = int(id)
    except ValueError:
        return "Invalid ID", 400

    # Get context and query parameters
    context = request.args.get("context")
    query = request.args.get("query", "")

    # Fetch metadata from the database
    metadata = fetch_metadata_by_id(id)
    if not metadata:
        return "Image not found", 404

    image_path = metadata["image_path"]
    image_tags = metadata["tags"]

    # Determine media type
    file_extension = os.path.splitext(os.path.basename(image_path))[1].lower()
    media_type = "image" if file_extension in [".jpg", ".jpeg", ".png", ".gif"] else "video"

    # Handle cases where context is not provided
    if not context:
        for tag in image_tags:
            tag_list.append([tag,fetch_tag_count(tag.strip()),colorcode(tag.strip())])
        
        tag_list = sorted(tag_list, key=lambda x: (colororder.index(x[2]), -x[1], x[0]))
        return render_template(
            "result.html",
            image_path=image_path,
            image_tags=tag_list,
            mediatype=media_type,
            next_link=None,
            prev_link=None,
            context=None,
            query=None
        )

    # Determine the image list based on the context
    if context == "allofthem":
        image_list = fetch_all_images_with_idsfr()  # Fetch all images and IDs
        image_ids = [img["id"] for img in image_list]
    elif context == "favorites":
        image_ids = fetch_favorite_image_ids()
    elif context == "search":
        with open("./database/cached_queries.json", "r") as json_file:
            cached_searches = json.load(json_file)
        if(query not in cached_searches):
            # Fetch matching images using the universal function
            image_ids = search_images_with_conditions(query,onlyids=True)
        else:
            image_ids = cached_searches[query]
    else:
        return "Invalid context", 400

    # Find the current image's index
    try:
        current_index = image_ids.index(id)
    except ValueError:
        if context == "search":
            return redirect(f"/{context}/{query}/")
        else:
            return redirect(f"/{context}/")

    # Determine the next and previous IDs
    next_id = image_ids[(current_index + 1) % len(image_ids)]
    prev_id = image_ids[(current_index - 1) % len(image_ids)]

    # Generate the next/previous links
    next_link = f"/result/{next_id}?context={context}&query={query}"
    prev_link = f"/result/{prev_id}?context={context}&query={query}"

    for tag in image_tags:
        tag_list.append([tag,fetch_tag_count(tag.strip()),colorcode(tag.strip())])
        
    tag_list = sorted(tag_list, key=lambda x: (colororder.index(x[2]), -x[1], x[0]))

    return render_template(
        "result.html",
        image_path=image_path,
        image_tags=tag_list,
        mediatype=media_type,
        next_link=next_link,
        prev_link=prev_link,
        context=context,
        query=query,
        pagetype = "result"
    )

@app.route("/delete/<id>")
def delete_file(id):
    if delete_image_by_id(id):  # Delete image using the ID
        return redirect(request.args.get("redirect", "/"))
    else:
        return "Error: Image not found", 404

@app.route("/edit/<id>", methods=["POST"])
def edit_tags(id):
    updated_tags = request.form.get("tags", "").strip().split()

    # Fetch the image path using the ID
    image_path = fetch_image_path_by_id(id)
    if not image_path:
        return "Error: Image not found", 404

    # Call process_edit_tags to update the tags
    process_edit_tags(image_path, updated_tags)

    # Redirect to the referring page
    return redirect(request.args.get("redirect", "/"))

@app.route('/favorite', methods=['POST'])
def favImg():
    data = request.get_json()
    image_id = data.get("imageID")  # Get the image ID from the request
    if image_id:
        # Add the image to the favorites table
        add_to_favorites(image_id)
        return jsonify({"message": "Image added to favorites.", "ImageId": image_id}), 200
    else:
        return jsonify({"error": "Invalid image ID."}), 400

@app.route('/unfavorite', methods=['DELETE'])
def unFavImg():
    data = request.get_json()
    image_id = data.get("imageID")  # Get the image ID from the request

    if image_id:
        # Remove the image from the favorites table
        remove_from_favorites(image_id)
        return jsonify({"message": "Image removed from favorites.", "ImageId": image_id}), 200
    else:
        return jsonify({"error": "Invalid image ID."}), 400


@app.route('/favorite-status', methods=['POST'])
def get_favorite_status():
    data = request.get_json()
    image_id = data.get("imageID")  # Get the image ID from the request

    if image_id:
        # Check if the image is favorited
        favorite_ids = fetch_favorite_image_ids()
        is_favorited = int(image_id) in favorite_ids
        return jsonify({"isFavorited": is_favorited}), 200
    else:
        return jsonify({"error": "Invalid image ID."}), 400


if __name__ == "__main__":
    initialize_database()
    app.run(host="0.0.0.0", port=port)
