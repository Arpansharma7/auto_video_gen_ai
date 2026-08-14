import os
import json
import time
import shutil
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow

# --- CONFIGURATION ---
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRETS_FILE = "client_secrets.json"
VIDEO_FOLDER = "./to_upload"
UPLOADED_FOLDER = "./uploaded_videos"
VIDEO_CATEGORY_ID = "22" # 22 is 'People & Blogs'
PRIVACY_STATUS = "public" # had more options to choose from :  "public", "private", "unlisted"

def get_authenticated_service():
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    credentials = flow.run_local_server(port=0)
    return build("youtube", "v3", credentials=credentials)

def upload_video(youtube, file_path, metadata):
    body = {
        "snippet": {
            "title": metadata.get("title", "Default Title"),
            "description": metadata.get("description", ""),
            "tags": [str(tag) for tag in metadata.get("tags", [])],
            "categoryId": VIDEO_CATEGORY_ID
        },
        "status": {
            "privacyStatus": PRIVACY_STATUS,
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(file_path, chunksize=-1, resumable=True, mimetype="video/*")
    
    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploading {os.path.basename(file_path)}: {int(status.progress() * 100)}%")

    print(f"Upload Complete! Video ID: {response.get('id')}")
    return True

def main():
    if not os.path.exists(UPLOADED_FOLDER):
        os.makedirs(UPLOADED_FOLDER)

    video_path = os.path.join(VIDEO_FOLDER, "video.mp4")
    metadata_path = os.path.join(VIDEO_FOLDER, "metadata.json")
    
    if not os.path.exists(video_path):
        print("No video.mp4 found in the upload folder.")
        return

    # Load AI generated metadata
    metadata = {}
    if os.path.exists(metadata_path):
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    else:
        print("No metadata.json found. Using defaults.")

    print("Authenticating with YouTube...")
    youtube = get_authenticated_service()
    print("Authentication successful!")

    print(f"\nStarting upload for: {video_path}")
    try:
        success = upload_video(youtube, video_path, metadata)
        if success:
            # Move video to uploaded folder to prevent re-uploading
            dest_path = os.path.join(UPLOADED_FOLDER, f"video_{int(time.time())}.mp4")
            shutil.move(video_path, dest_path)
            print(f"Moved video to {dest_path}")
    except Exception as e:
        print(f"An error occurred uploading {video_path}: {e}")

if __name__ == "__main__":
    main()