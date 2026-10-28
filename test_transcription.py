
from video_processor import transcribe_video
import glob
import os

uploads_folder = os.path.join(os.path.dirname(__file__), "uploads")
videos = glob.glob(os.path.join(uploads_folder, "*"))

if not videos:
    print("No uploaded videos found. Upload a video first.")
else:
    video_path = videos[0]
    print("Processing:", os.path.basename(video_path))

    try:
        result = transcribe_video(video_path)

        print("\nTranscription completed!")
        print("Detected language:", result["language"])
        print("Transcript saved to:", result["transcript_path"])
        print("\nTranscript preview:")

        for segment in result["segments"][:10]:
            print(f"{segment['start']:.2f}s: {segment['text']}")

    except Exception as error:
        print("Processing failed:", error)
