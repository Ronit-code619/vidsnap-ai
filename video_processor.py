
import os
import subprocess
from faster_whisper import WhisperModel

# Shared storage directory: local folders by default, configurable in production
STORAGE_ROOT = os.path.abspath(
    os.getenv("VIDSNAP_STORAGE_DIR", os.path.dirname(__file__))
)

UPLOAD_FOLDER = os.path.join(STORAGE_ROOT, "uploads")
PROCESSED_FOLDER = os.path.join(STORAGE_ROOT, "processed")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

def transcribe_video(video_path):
    if not os.path.isfile(video_path):
        raise FileNotFoundError("Uploaded video was not found.")

    video_name = os.path.splitext(os.path.basename(video_path))[0]
    audio_path = os.path.join(PROCESSED_FOLDER, video_name + ".wav")
    transcript_path = os.path.join(PROCESSED_FOLDER, video_name + ".txt")

    # Extract audio from the video using FFmpeg
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-vn",
            "-ac", "1",
            "-ar", "16000",
            audio_path,
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    # Load the speech-recognition model
    model = WhisperModel(
        "base",
        device="cpu",
        compute_type="int8",
    )

    # Convert speech into text
    segments, info = model.transcribe(
        audio_path,
        beam_size=5,
    )

    transcript_segments = []

    with open(transcript_path, "w", encoding="utf-8") as output:
        output.write(f"Detected language: {info.language}\n\n")

        for segment in segments:
            line = f"[{segment.start:.2f} - {segment.end:.2f}] {segment.text.strip()}"
            output.write(line + "\n")
            transcript_segments.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip(),
            })

    return {
        "audio_path": audio_path,
        "transcript_path": transcript_path,
        "language": info.language,
        "segments": transcript_segments,
    }

import subprocess
import os


def create_video_clip(
    video_path,
    start_seconds,
    duration_seconds,
    output_path,
    subtitle_path=None,
):
    """Cut a video segment and format it for vertical social media."""

    if not os.path.isfile(video_path):
        raise FileNotFoundError("Source video not found.")

    if start_seconds < 0:
        raise ValueError("Start time cannot be negative.")

    if not 5 <= duration_seconds <= 60:
        raise ValueError("Clip duration must be between 5 and 60 seconds.")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    command = [
        "ffmpeg",
        "-y",
        "-ss", str(start_seconds),
        "-i", video_path,
        "-t", str(duration_seconds),
        "-map", "0:v:0",
        "-map", "0:a:0?",
        "-vf",
        (
        "scale=720:1280:force_original_aspect_ratio=increase,"
        "crop=720:1280"
    +   (
        ",subtitles='"
        + os.path.abspath(subtitle_path)
            .replace("\\", "/")
            .replace(":", r"\:")
            .replace("'", r"\'")
        + "':force_style='FontName=Arial,FontSize=18,"
          "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
          "BorderStyle=1,Outline=2,Shadow=1,"
          "Alignment=2,MarginV=100'"
        if subtitle_path
        else ""
        )
        ),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        output_path,
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(
            "FFmpeg video processing failed: " + result.stderr[-2000:]
        )

    return output_path


import re


def find_hooks(transcript_segments, limit=8):
    """
    Rank potential short-video moments using transcript text and timestamps.
    Combines adjacent speech segments so complete thoughts can be selected.
    """

    patterns = {
        "Question": (
            r"\?|"
            r"\b(why|how|what if|did you know|have you ever|"
            r"kya|kyun|kaise|kaisa|kaisi)\b"
        ),
        "Attention Grabber": (
            r"\b(secret|mistake|shocking|surprising|truth|never|"
            r"stop|imagine|challenge|catch|simple)\b|"
            r"\b(sach|galti|socho|kabhi nahi|ruk jao)\b"
        ),
        "Useful Advice": (
            r"\b(how to|the reason|because|the solution|step|tip|"
            r"learn|plan|study|practice|understood)\b|"
            r"\b(kaise karein|solution|tarika|seekho|samjho)\b"
        ),
        "Memorable Statement": (
            r"\b(if you|you can|you'll|you have|the point is|"
            r"the secret is|the truth is|that's why)\b|"
            r"\b(win your|changed your|believe in you|"
            r"trajectory|flow state)\b"
        ),
    }

    # Convert Faster-Whisper segments or dictionaries into a common format.
    segments = []

    for segment in transcript_segments:
        if isinstance(segment, dict):
            start = float(segment.get("start", 0))
            end = float(segment.get("end", start))
            text = str(segment.get("text", "")).strip()
        else:
            start = float(getattr(segment, "start", 0))
            end = float(getattr(segment, "end", start))
            text = str(getattr(segment, "text", "")).strip()

        if text and end >= start:
            segments.append({
                "start": start,
                "end": end,
                "text": text
            })

    if not segments:
        return []

    # Combine neighboring segments into short, coherent speech windows.
    windows = []
    max_window_seconds = 20
    max_window_words = 55

    for i, first in enumerate(segments):
        combined_text = first["text"]
        start = first["start"]
        end = first["end"]

        windows.append({
            "start": start,
            "end": end,
            "text": combined_text
        })

        for next_segment in segments[i + 1:]:
            proposed_end = next_segment["end"]
            proposed_text = combined_text + " " + next_segment["text"]

            if proposed_end - start > max_window_seconds:
                break

            if len(proposed_text.split()) > max_window_words:
                break

            # Avoid combining segments separated by a long silence.
            if next_segment["start"] - end > 2.5:
                break

            combined_text = proposed_text
            end = proposed_end

            windows.append({
                "start": start,
                "end": end,
                "text": combined_text
            })

    candidates = []

    for window in windows:
        text = window["text"].strip()
        normalized = text.lower()
        word_count = len(text.split())
        duration = window["end"] - window["start"]

        if word_count < 5 or duration <= 0:
            continue

        matched_types = [
            hook_type
            for hook_type, pattern in patterns.items()
            if re.search(pattern, normalized, re.IGNORECASE)
        ]

        score = len(matched_types) * 2

        # Favor clips with a clear, useful amount of speech.
        if 8 <= word_count <= 35:
            score += 2

        if "?" in text:
            score += 2

        # Recognize short, memorable motivational statements.
        if re.search(
            r"\b(if you win|you win your|the point is|"
            r"believe in you|you've literally changed)\b",
            normalized
        ):
            score += 3
            if "Memorable Statement" not in matched_types:
                matched_types.append("Memorable Statement")

        if not matched_types:
            continue

        # Prefer clips that can stand alone without becoming too long.
        if duration > 20:
            score -= 2

        candidates.append({
            "start_seconds": max(0, int(window["start"])),
            "end_seconds": round(window["end"], 2),
            "duration": max(1, round(duration)),
            "text": text,
            "hook_type": matched_types[0],
            "score": max(1, score),
        })

    # Rank the strongest candidates first.
    candidates.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    selected = []

    for candidate in candidates:
        # Avoid nearly identical overlapping suggestions.
        overlaps = any(
            candidate["start_seconds"] < item["end_seconds"]
            and item["start_seconds"] < candidate["end_seconds"]
            for item in selected
        )

        if not overlaps:
            selected.append(candidate)

        if len(selected) >= limit:
            break

    selected.sort(key=lambda item: item["start_seconds"])
    return selected


def format_srt_timestamp(seconds):
    """Convert seconds to the SRT timestamp format."""
    milliseconds = round(max(0, float(seconds)) * 1000)

    hours = milliseconds // 3_600_000
    milliseconds %= 3_600_000

    minutes = milliseconds // 60_000
    milliseconds %= 60_000

    whole_seconds = milliseconds // 1000
    milliseconds %= 1000

    return (
        f"{hours:02}:{minutes:02}:"
        f"{whole_seconds:02},{milliseconds:03}"
    )


def create_srt_captions(
    transcript_segments,
    clip_start_seconds,
    clip_duration_seconds,
    output_path,
):
    """
    Create an SRT subtitle file for a selected video clip.

    Transcript timestamps are relative to the original video.
    Output timestamps are relative to the start of the clip.
    """

    clip_start = max(0.0, float(clip_start_seconds))
    clip_end = clip_start + float(clip_duration_seconds)

    subtitles = []

    for segment in transcript_segments:
        if isinstance(segment, dict):
            start = float(segment.get("start", 0))
            end = float(segment.get("end", start))
            text = str(segment.get("text", "")).strip()
        else:
            start = float(getattr(segment, "start", 0))
            end = float(getattr(segment, "end", start))
            text = str(getattr(segment, "text", "")).strip()

        # Keep only speech that overlaps the selected clip.
        adjusted_start = max(start, clip_start)
        adjusted_end = min(end, clip_end)

        if not text or adjusted_end <= adjusted_start:
            continue

        # Shift timestamps to begin at zero for the new clip.
        relative_start = adjusted_start - clip_start
        relative_end = adjusted_end - clip_start

        subtitles.append({
            "start": relative_start,
            "end": relative_end,
            "text": text,
        })

    os.makedirs(
        os.path.dirname(os.path.abspath(output_path)),
        exist_ok=True,
    )

    with open(output_path, "w", encoding="utf-8") as subtitle_file:
        for index, subtitle in enumerate(subtitles, start=1):
            subtitle_file.write(f"{index}\n")
            subtitle_file.write(
                f"{format_srt_timestamp(subtitle['start'])} --> "
                f"{format_srt_timestamp(subtitle['end'])}\n"
            )
            subtitle_file.write(subtitle["text"] + "\n\n")

    return output_path
