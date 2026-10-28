
import glob
import os
from video_processor import create_video_clip

project_folder = os.path.dirname(os.path.abspath(__file__))
uploads_folder = os.path.join(project_folder, "uploads")
output_folder = os.path.join(project_folder, "processed")

videos = glob.glob(os.path.join(uploads_folder, "*.mp4"))

if not videos:
    print("No MP4 video found in uploads.")
else:
    source_video = videos[0]
    output_video = os.path.join(output_folder, "test_reel.mp4")

    try:
        create_video_clip(
            video_path=source_video,
            start_seconds=0,
            duration_seconds=15,
            output_path=output_video,
        )

        print("Clip created successfully!")
        print("Output:", output_video)
        print("File size:", os.path.getsize(output_video), "bytes")

    except Exception as error:
        print("Clip creation failed:", error)
