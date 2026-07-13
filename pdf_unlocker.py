#!/usr/bin/env python3
"""CLI pour deverrouiller des fichiers PDF proteges par mot de passe via qpdf."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


class PDFUnlockError(Exception):
    """Erreur levee lors du deverrouillage d'un PDF."""


def check_qpdf_installed() -> None:
    if shutil.which("qpdf") is None:
        raise PDFUnlockError(
            "qpdf est introuvable. Installez-le avec 'sudo apt install qpdf' "
            "(Linux), 'brew install qpdf' (macOS) ou depuis "
            "https://qpdf.sourceforge.io/ (Windows)."
        )


def validate_input_file(pdf_path: Path) -> None:
    if not pdf_path.exists():
        raise PDFUnlockError(f"Fichier introuvable : {pdf_path}")
    if not pdf_path.is_file():
        raise PDFUnlockError(f"Le chemin n'est pas un fichier : {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise PDFUnlockError(f"Le fichier n'est pas un PDF : {pdf_path}")
    if not os_access_readable(pdf_path):
        raise PDFUnlockError(f"Permission de lecture refusee : {pdf_path}")


def os_access_readable(path: Path) -> bool:
    import os

    return os.access(path, os.R_OK)


def build_output_path(pdf_path: Path) -> Path:
    return pdf_path.with_name(f"{pdf_path.stem}_deverrouille{pdf_path.suffix}")


def format_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("o", "Ko", "Mo", "Go"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} To"


def unlock_pdf(pdf_path: Path, password: str, output_path: Path | None = None) -> Path:
    """Deverrouille un PDF protege par mot de passe avec qpdf.

    Retourne le chemin du fichier deverrouille en cas de succes.
    Leve PDFUnlockError en cas d'echec (mot de passe incorrect, etc.).
    """
    check_qpdf_installed()
    validate_input_file(pdf_path)

    output_path = output_path or build_output_path(pdf_path)

    with tempfile.TemporaryDirectory(prefix="pdf_unlocker_") as tmp_dir:
        tmp_output = Path(tmp_dir) / output_path.name

        cmd = [
            "qpdf",
            f"--password={password}",
            "--decrypt",
            str(pdf_path),
            str(tmp_output),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        stderr = result.stderr.strip()

        if result.returncode != 0:
            if "invalid password" in stderr.lower():
                raise PDFUnlockError("Mot de passe incorrect.")
            if "permission denied" in stderr.lower():
                raise PDFUnlockError(f"Permissions insuffisantes pour ecrire le fichier : {output_path}")
            raise PDFUnlockError(f"echec de qpdf : {stderr or 'erreur inconnue'}")

        if not tmp_output.exists():
            raise PDFUnlockError("qpdf n'a produit aucun fichier de sortie.")

        try:
            shutil.move(str(tmp_output), str(output_path))
        except PermissionError as exc:
            raise PDFUnlockError(f"Permissions insuffisantes pour ecrire le fichier : {output_path}") from exc

    return output_path


def process_single_file(pdf_path: Path, password: str) -> bool:
    """Traite un seul fichier PDF, affiche la progression. Retourne True si succes."""
    print(f"\nTraitement de : {pdf_path.name}")
    try:
        original_size = pdf_path.stat().st_size
    except OSError:
        original_size = None

    try:
        output_path = unlock_pdf(pdf_path, password)
    except PDFUnlockError as exc:
        print(f"  Echec : {exc}")
        return False

    new_size = output_path.stat().st_size
    print(f"  Succes : {output_path.name}")
    if original_size is not None:
        print(f"  Taille avant : {format_size(original_size)}  ->  apres : {format_size(new_size)}")
    return True


def process_batch(pdf_paths: list[Path], password: str) -> None:
    total = len(pdf_paths)
    success_count = 0
    for pdf_path in pdf_paths:
        if process_single_file(pdf_path, password):
            success_count += 1

    print(f"\nTermine : {success_count}/{total} fichier(s) deverrouille(s) avec succes.")


def prompt_interactive() -> tuple[list[Path], str]:
    import getpass

    raw_paths = input("Chemin du/des fichier(s) PDF (separes par une virgule si plusieurs) : ").strip()
    paths = [Path(p.strip().strip('"').strip("'")) for p in raw_paths.split(",") if p.strip()]
    if not paths:
        raise PDFUnlockError("Aucun fichier fourni.")
    password = getpass.getpass("Mot de passe : ")
    return paths, password


def show_help() -> None:
    print(__doc__)
    print("Usage :")
    print("  python pdf_unlocker.py                              # mode interactif")
    print("  python pdf_unlocker.py fichier.pdf                  # mode drag-and-drop (mot de passe demande)")
    print("  python pdf_unlocker.py fichier.pdf motdepasse        # mode CLI")
    print("  python pdf_unlocker.py f1.pdf f2.pdf ... motdepasse  # mode batch (meme mot de passe)")


def parse_cli_args(argv: list[str]) -> tuple[list[Path], str | None]:
    """Distingue les fichiers du mot de passe dans une liste d'arguments bruts.

    Le dernier argument est considere comme le mot de passe, sauf s'il
    correspond lui-meme a un chemin de fichier .pdf (auquel cas tous les
    arguments sont des fichiers et le mot de passe sera demande de facon
    interactive).
    """
    if len(argv) == 1:
        return [Path(argv[0])], None

    last = argv[-1]
    if Path(last).suffix.lower() == ".pdf":
        return [Path(a) for a in argv], None

    return [Path(a) for a in argv[:-1]], last


def main() -> int:
    argv = sys.argv[1:]

    if argv and argv[0] in ("-h", "--help"):
        show_help()
        return 0

    try:
        if not argv:
            # Mode interactif : aucun argument fourni.
            pdf_paths, password = prompt_interactive()
        else:
            pdf_paths, password = parse_cli_args(argv)
            if password is None:
                # Mode drag-and-drop : fichier(s) fournis, mot de passe manquant.
                import getpass

                password = getpass.getpass("Mot de passe : ")
    except (PDFUnlockError, KeyboardInterrupt, EOFError) as exc:
        print(f"Erreur : {exc}" if isinstance(exc, PDFUnlockError) else "\nAnnule.")
        return 1

    if not password:
        print("Erreur : le mot de passe ne peut pas etre vide.")
        return 1

    if len(pdf_paths) == 1:
        success = process_single_file(pdf_paths[0], password)
        return 0 if success else 1

    process_batch(pdf_paths, password)
    return 0


if __name__ == "__main__":
    sys.exit(main())
