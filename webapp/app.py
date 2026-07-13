"""Interface web Flask pour deverrouiller des PDF via pdf_unlocker.py."""

import shutil
import sys
import tempfile
import threading
import time
import uuid
import zipfile
from pathlib import Path

from flask import Flask, abort, render_template, request, send_from_directory, url_for

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pdf_unlocker import PDFUnlockError, format_size, unlock_pdf  # noqa: E402

UPLOAD_ROOT = Path(tempfile.gettempdir()) / "pdf_unlocker_web"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
SESSION_TTL_SECONDS = 15 * 60
CLEANUP_INTERVAL_SECONDS = 60

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 Mo max par requete


def cleanup_old_sessions() -> None:
    while True:
        now = time.time()
        for session_dir in UPLOAD_ROOT.iterdir():
            try:
                if session_dir.is_dir() and now - session_dir.stat().st_mtime > SESSION_TTL_SECONDS:
                    shutil.rmtree(session_dir, ignore_errors=True)
            except FileNotFoundError:
                continue
        time.sleep(CLEANUP_INTERVAL_SECONDS)


threading.Thread(target=cleanup_old_sessions, daemon=True).start()


def safe_component(name: str) -> str | None:
    """Reduit un nom fourni par l'utilisateur a un simple composant de chemin sur."""
    candidate = Path(name).name
    if not candidate or candidate in (".", ".."):
        return None
    return candidate


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/unlock", methods=["POST"])
def unlock():
    password = request.form.get("password", "")
    uploaded_files = [f for f in request.files.getlist("pdfs") if f and f.filename]

    if not password:
        return render_template("index.html", error="Le mot de passe ne peut pas etre vide.")
    if not uploaded_files:
        return render_template("index.html", error="Merci de choisir au moins un fichier PDF.")

    session_id = uuid.uuid4().hex
    session_dir = UPLOAD_ROOT / session_id
    session_dir.mkdir(parents=True)

    results = []
    for uploaded in uploaded_files:
        original_name = safe_component(uploaded.filename)
        if original_name is None:
            results.append({"name": uploaded.filename, "ok": False, "message": "Nom de fichier invalide."})
            continue
        if Path(original_name).suffix.lower() != ".pdf":
            results.append({"name": original_name, "ok": False, "message": "Ce n'est pas un fichier PDF."})
            continue

        input_path = session_dir / original_name
        uploaded.save(input_path)
        original_size = input_path.stat().st_size

        output_name = f"{input_path.stem}_deverrouille{input_path.suffix}"
        output_path = session_dir / output_name

        try:
            unlock_pdf(input_path, password, output_path=output_path)
        except PDFUnlockError as exc:
            results.append({"name": original_name, "ok": False, "message": str(exc)})
        else:
            new_size = output_path.stat().st_size
            results.append(
                {
                    "name": original_name,
                    "ok": True,
                    "output_name": output_name,
                    "size_before": format_size(original_size),
                    "size_after": format_size(new_size),
                    "download_url": url_for("download", session_id=session_id, filename=output_name),
                }
            )
        finally:
            input_path.unlink(missing_ok=True)

    success_count = sum(1 for r in results if r["ok"])
    zip_url = None
    if success_count > 1:
        zip_path = session_dir / "pdfs_deverrouilles.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for r in results:
                if r["ok"]:
                    zf.write(session_dir / r["output_name"], arcname=r["output_name"])
        zip_url = url_for("download", session_id=session_id, filename=zip_path.name)

    return render_template(
        "index.html",
        results=results,
        zip_url=zip_url,
        success_count=success_count,
        total_count=len(results),
    )


@app.route("/download/<session_id>/<path:filename>")
def download(session_id, filename):
    safe_session = safe_component(session_id)
    safe_name = safe_component(filename)
    if safe_session is None or safe_name is None:
        abort(404)

    session_dir = (UPLOAD_ROOT / safe_session).resolve()
    if session_dir.parent != UPLOAD_ROOT.resolve():
        abort(404)

    file_path = session_dir / safe_name
    if not file_path.is_file():
        abort(404)

    return send_from_directory(session_dir, safe_name, as_attachment=True)


@app.errorhandler(413)
def too_large(_error):
    return render_template("index.html", error="Fichier(s) trop volumineux (limite : 200 Mo)."), 413


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
