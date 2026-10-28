from video_processor import (
    transcribe_video,
    create_video_clip,
    find_hooks,
    create_srt_captions,
)
from video_processor import transcribe_video
import uuid
from flask import send_from_directory
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import os


load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("SECRET_KEY environment variable must be set")

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


db = SQLAlchemy(app)

# =========================
# VIDEO UPLOAD CONFIGURATION
# =========================

STORAGE_ROOT = os.path.abspath(
    os.getenv("VIDSNAP_STORAGE_DIR", app.root_path)
)

UPLOAD_FOLDER = os.path.join(STORAGE_ROOT, "uploads")
PROCESSED_FOLDER = os.path.join(STORAGE_ROOT, "processed")

ALLOWED_VIDEO_EXTENSIONS = {"mp4", "mov", "avi", "mkv", "webm"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["PROCESSED_FOLDER"] = PROCESSED_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)


def allowed_video(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_VIDEO_EXTENSIONS
    )
# =========================
# USER MODEL
# =========================

class User(db.Model):

    __tablename__ = "users"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(255),
        unique=True,
        nullable=False
    )
    country = db.Column(
        db.String(100),
        nullable=True
    )
    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp()
    )


class Video(db.Model):
    __tablename__ = "videos"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    title = db.Column(db.String(255), nullable=True)
    duration_seconds = db.Column(db.Numeric(10, 2), nullable=True)
    detected_language = db.Column(db.String(50), nullable=True)
    processing_status = db.Column(
        db.String(20),
        nullable=False,
        default="uploaded",
    )
    created_at = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp(),
    )
    updated_at = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )


class TranscriptSegment(db.Model):
    __tablename__ = "transcript_segments"

    id = db.Column(db.BigInteger, primary_key=True)
    video_id = db.Column(
        db.Integer,
        db.ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_seconds = db.Column(db.Numeric(10, 3), nullable=False)
    end_seconds = db.Column(db.Numeric(10, 3), nullable=False)
    transcript_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp(),
    )

class GeneratedClip(db.Model):
    __tablename__ = "generated_clips"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    video_id = db.Column(
        db.Integer,
        db.ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    stored_filename = db.Column(
        db.String(255),
        nullable=False,
        unique=True,
    )

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp(),
        nullable=False,
    )

# Your other routes start below here

# -----------------------------
# Debug information
# -----------------------------



# =========================================================
# PAGES
# =========================================================


@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        flash("Please log in first.", "error")
        return redirect(url_for("login"))

    return render_template(
        "dashboard.html",
        user_name=session.get("user_name")
    )

@app.route("/projects")
def projects():
    return render_template("projects.html")


@app.route("/analytics")
def analytics():
    return render_template("analytics.html")


@app.route("/profile")
def profile():

    if "user_id" not in session:
        flash("Please log in first.", "error")
        return redirect(url_for("login"))

    user = db.session.get(
        User,
        session["user_id"]
    )

    return render_template(
        "profile.html",
        user=user
    )


@app.route("/update-profile", methods=["POST"])
def update_profile():
    if "user_id" not in session:
        flash("Please log in first.", "error")
        return redirect(url_for("login"))

    user = db.session.get(User, session["user_id"])

    if user is None:
        session.clear()
        flash("User account not found. Please log in again.", "error")
        return redirect(url_for("login"))

    name = request.form.get("name", "").strip()
    country = request.form.get("country", "").strip()

    if not name:
        flash("Name cannot be empty.", "error")
        return redirect(url_for("profile"))

    user.name = name
    user.country = country or None

    try:
        db.session.commit()
        session["user_name"] = user.name
        flash("Profile updated successfully!", "success")
    except Exception:
        db.session.rollback()
        flash("Could not update your profile. Please try again.", "error")

    return redirect(url_for("profile"))


@app.route("/settings")
def settings():
    return render_template("settings.html")


@app.route("/pricing")
def pricing():
    return render_template("pricing.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/faq")
def faq():
    return render_template("faq.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/cookies")
def cookies():
    return render_template("cookies.html")


@app.route("/forgot-password")
def forgot_password():
    return render_template("forgot_password.html")


@app.route("/verify-email")
def verify_email():
    return render_template("verify_email.html")





@app.route("/processing", methods=["GET", "POST"])
def processing():
    if "user_id" not in session:
        flash("Please log in first.", "error")
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template(
            "processing.html",
            processing_complete=False,
            hook_suggestions=[],
        )

    video_record = None

    try:
        filename = session.get("last_uploaded_video")

        if not filename:
            flash("Please upload a video first.", "error")
            return redirect(url_for("upload"))

        video_record = Video.query.filter_by(
            user_id=session["user_id"],
            stored_filename=filename,
        ).first()

        if video_record is None:
            flash("Video record not found. Please upload it again.", "error")
            return redirect(url_for("upload"))

        video_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            video_record.stored_filename,
        )

        if not os.path.isfile(video_path):
            flash(
                "Uploaded video could not be found. Please upload it again.",
                "error",
            )
            return redirect(url_for("upload"))

        video_record.processing_status = "processing"
        db.session.commit()

        result = transcribe_video(video_path)

        transcript_segments = result["segments"]
        detected_language = result["language"]
        transcript_path = result["transcript_path"]

        # Replace existing transcript segments for this video.
        TranscriptSegment.query.filter_by(
            video_id=video_record.id
        ).delete(synchronize_session=False)

        for segment in transcript_segments:
            db.session.add(
                TranscriptSegment(
                    video_id=video_record.id,
                    start_seconds=segment["start"],
                    end_seconds=segment["end"],
                    transcript_text=segment["text"],
                )
            )

        video_record.detected_language = detected_language
        video_record.processing_status = "completed"
        db.session.commit()

        hook_suggestions = find_hooks(transcript_segments)

        return render_template(
            "processing.html",
            transcript_segments=transcript_segments,
            detected_language=detected_language,
            transcript_path=transcript_path,
            processing_complete=True,
            hook_suggestions=hook_suggestions,
        )

    except Exception:
        db.session.rollback()
        app.logger.exception("AI video transcription failed")

        if video_record is not None:
            try:
                video_record.processing_status = "failed"
                db.session.commit()
            except Exception:
                db.session.rollback()
                app.logger.exception(
                    "Could not update video processing status"
                )

        flash(
            "Video processing failed. Check the VS Code terminal for details.",
            "error",
        )
        return redirect(url_for("upload"))




@app.route("/generate-clip", methods=["POST"])
def generate_clip():
    if "user_id" not in session:
        flash("Please log in first.", "error")
        return redirect(url_for("login"))


    requested_video_id = request.form.get("video_id", "").strip()

    if requested_video_id:
        try:
            requested_video_id = int(requested_video_id)
        except ValueError:
            flash("Invalid video selection.", "error")
            return redirect(url_for("creator_memory"))

        video_record = Video.query.filter_by(
            id=requested_video_id,
            user_id=session["user_id"],
        ).first()

        if video_record is None:
            flash("Video not found in your library.", "error")
            return redirect(url_for("creator_memory"))

        saved_name = video_record.stored_filename
    else:
        # Preserve existing Hook Finder and Upload Studio behavior.
        saved_name = session.get("last_uploaded_video")

        if not saved_name:
            flash("Please upload a video first.", "error")
            return redirect(url_for("upload"))

        video_record = Video.query.filter_by(
            user_id=session["user_id"],
            stored_filename=saved_name,
        ).first()

        # Allow previously uploaded files that predate Creator Memory.
        if video_record is None:
            app.logger.warning(
                "No video database record found for %s", saved_name
            )

    video_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        saved_name,
    )

    if not os.path.isfile(video_path):
        flash("Uploaded video not found. Please upload it again.", "error")
        return redirect(url_for("upload"))
    try:
        start_seconds = float(request.form.get("start_seconds", "0"))
        duration = int(request.form.get("duration", "15"))

        if start_seconds < 0 or start_seconds > 86400:
            raise ValueError("Choose a valid start time.")

        if not 5 <= duration <= 60:
            raise ValueError(
                "Clip duration must be between 5 and 60 seconds."
            )

        # Captions will be enabled by a checkbox added in the next step.
        captions_enabled = request.form.get("captions") == "on"

        output_name = f"{uuid.uuid4().hex}.mp4"
        output_path = os.path.join(app.config["PROCESSED_FOLDER"], output_name)

        subtitle_path = None

        if captions_enabled:
            # Generate timestamped captions for the source video.
            result = transcribe_video(video_path)

            subtitle_name = f"{uuid.uuid4().hex}.srt"
            subtitle_path = os.path.join(app.config["PROCESSED_FOLDER"], subtitle_name)

            create_srt_captions(
                transcript_segments=result["segments"],
                clip_start_seconds=start_seconds,
                clip_duration_seconds=duration,
                output_path=subtitle_path,
            )


        create_video_clip(
            video_path=video_path,
            start_seconds=start_seconds,
            duration_seconds=duration,
            output_path=output_path,
            subtitle_path=subtitle_path,
        )

        if video_record is None:
            raise RuntimeError(
                "Cannot register clip without a saved source-video record."
            )

        generated_clip = GeneratedClip(
            user_id=session["user_id"],
            video_id=video_record.id,
            stored_filename=output_name,
        )

        db.session.add(generated_clip)
        db.session.commit()

        return render_template(
            "clip_result.html",
            clip_url=url_for("preview_clip", filename=output_name),
            download_url=url_for("download_clip", filename=output_name),
            duration=duration,
        )

    except (ValueError, TypeError) as error:
        flash(str(error), "error")
        return redirect(url_for("upload"))

    except Exception:
        app.logger.exception("Clip generation failed")
        flash(
            "Could not generate the clip. Check the VS Code terminal.",
            "error",
        )
        return redirect(url_for("upload"))



@app.route("/processed-video/<filename>")
def preview_clip(filename):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if (
        not filename.endswith(".mp4")
        or filename != os.path.basename(filename)
    ):
        return "Invalid filename", 400

    clip = GeneratedClip.query.filter_by(
        user_id=session["user_id"],
        stored_filename=filename,
    ).first()

    if clip is None:
        return "Clip not found", 404

    return send_from_directory(
        app.config["PROCESSED_FOLDER"],
        filename,
        as_attachment=False,
    )


@app.route("/download-clip/<filename>")
def download_clip(filename):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if (
        not filename.endswith(".mp4")
        or filename != os.path.basename(filename)
    ):
        return "Invalid filename", 400

    clip = GeneratedClip.query.filter_by(
        user_id=session["user_id"],
        stored_filename=filename,
    ).first()

    if clip is None:
        return "Clip not found", 404

    return send_from_directory(
        app.config["PROCESSED_FOLDER"],
        filename,
        as_attachment=True,
        download_name="VidSnap_AI_Reel.mp4",
    )




@app.route("/download")
def download():
    return render_template("download.html")


@app.route("/404")
def error_page():
    return render_template("404.html")


@app.route("/maintenance")
def maintenance():
    return render_template("maintenance.html")


# =========================================================
# HOME
# =========================================================


@app.route("/")
def home():
    return render_template("index.html")


# =========================================================
# LOGIN
# =========================================================


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        # Check empty fields
        if not email or not password:
            flash("Please enter email and password.", "error")
            return redirect(url_for("login"))

        # Find user by email
        user = User.query.filter_by(email=email).first()

        # Check user and password
        if user and check_password_hash(
            user.password_hash,
            password
        ):

            # Create login session
            session["user_id"] = user.id
            session["user_name"] = user.name

            flash(
                f"Welcome back, {user.name}!",
                "success"
            )

            return redirect(url_for("dashboard"))

        else:

            flash(
                "Invalid email or password.",
                "error"
            )

            return redirect(url_for("login"))

    return render_template("login.html")

# =========================================================
# SIGNUP
# =========================================================
@app.route("/logout")
def logout():

    session.clear()

    flash("You have been logged out successfully.", "success")

    return redirect(url_for("login"))

@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":

        # Get data from signup form
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        # Remove extra spaces
        if name:
            name = name.strip()

        if email:
            email = email.strip().lower()

        # Check empty fields
        if not name or not email or not password or not confirm_password:

            flash("Please fill in all fields.", "error")

            return redirect(url_for("signup"))

        # Check password confirmation
        if password != confirm_password:

            flash("Passwords do not match.", "error")

            return redirect(url_for("signup"))

        # Check if email already exists
        existing_user = User.query.filter_by(
            email=email
        ).first()

        if existing_user:

            flash(
                "An account with this email already exists.",
                "error"
            )

            return redirect(url_for("signup"))

        # Convert password into a secure hash
        hashed_password = generate_password_hash(password)

        # Create new user
        new_user = User(
            name=name,
            email=email,
            password_hash=hashed_password
        )

        # Save user to MySQL
        try:

            db.session.add(new_user)

            db.session.commit()

            flash(
                "Account created successfully! Please log in.",
                "success"
            )

            return redirect(url_for("login"))

        except Exception as e:

            db.session.rollback()

            return f"Signup Error: {e}"

    # If user opens /signup normally
    return render_template("signup.html")

# =========================================================
# UPLOAD
# =========================================================




@app.route("/upload", methods=["GET", "POST"])
def upload():
    if "user_id" not in session:
        flash("Please log in before uploading a video.", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        video = request.files.get("video")

        if not video or not video.filename:
            flash("Please select a video first.", "error")
            return redirect(url_for("upload"))

        if not allowed_video(video.filename):
            flash(
                "Unsupported video format. Use MP4, MOV, AVI, MKV, or WEBM.",
                "error",
            )
            return redirect(url_for("upload"))

        original_name = secure_filename(video.filename)

        if not original_name:
            flash("Invalid filename.", "error")
            return redirect(url_for("upload"))

        extension = original_name.rsplit(".", 1)[1].lower()
        saved_name = f"{uuid.uuid4().hex}.{extension}"
        save_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            saved_name,
        )

        try:
            video.save(save_path)

            new_video = Video(
                user_id=session["user_id"],
                original_filename=original_name,
                stored_filename=saved_name,
                title=os.path.splitext(original_name)[0],
                processing_status="uploaded",
            )

            db.session.add(new_video)
            db.session.commit()

            session["last_uploaded_video"] = saved_name
            session["last_uploaded_video_id"] = new_video.id

        except Exception:
            db.session.rollback()
            app.logger.exception("Video upload or database save failed")

            if os.path.isfile(save_path):
                try:
                    os.remove(save_path)
                except OSError:
                    app.logger.exception(
                        "Could not remove video after failed upload"
                    )

            flash(
                "Could not save the video. Check the VS Code terminal.",
                "error",
            )
            return redirect(url_for("upload"))

        flash("Video uploaded successfully!", "success")

        return render_template(
            "upload.html",
            uploaded_video_url=url_for(
                "uploaded_video",
                filename=saved_name,
            ),
            uploaded_filename=original_name,
        )

    return render_template(
        "upload.html",
        uploaded_video_url=None,
    )


@app.route("/uploaded-video/<filename>")
def uploaded_video(filename):
    if "user_id" not in session:
        return redirect(url_for("login"))

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename,
        as_attachment=False
    )


@app.route("/creator-memory", methods=["GET"])
def creator_memory():
    if "user_id" not in session:
        flash("Please log in first.", "error")
        return redirect(url_for("login"))

    search_query = request.args.get("q", "").strip()
    results = []

    if search_query:
        if len(search_query) > 200:
            flash("Search query is too long.", "error")
            search_query = search_query[:200]

        results = (
            db.session.query(TranscriptSegment, Video)
            .join(
                Video,
                TranscriptSegment.video_id == Video.id,
            )
            .filter(
                Video.user_id == session["user_id"],
                TranscriptSegment.transcript_text.ilike(
                    f"%{search_query}%"
                ),
            )
            .order_by(
                Video.created_at.desc(),
                TranscriptSegment.start_seconds.asc(),
            )
            .limit(100)
            .all()
        )

    return render_template(
        "creator_memory.html",
        search_query=search_query,
        results=results,
    )


# =========================================================
# GALLERY
# =========================================================


@app.route("/gallery")
def gallery():
    return render_template("gallery.html")


# =========================================================
# EDITOR
# =========================================================


@app.route("/editor")
def editor():
    return render_template("editor.html")


# =========================================================
# DATABASE TEST
# =========================================================


@app.route("/db-test")
def db_test():
    try:
        db.session.execute(db.text("SELECT 1"))
        return "MySQL Database Connected Successfully!"
    except Exception:
        app.logger.exception("Database connectivity check failed")
        return "Database connection failed.", 503


# =========================================================
# RUN APPLICATION
# =========================================================


if __name__ == "__main__":

    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")
