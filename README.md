# PDFunlock

Application CLI Python pour deverrouiller automatiquement des fichiers PDF proteges par mot de passe, en s'appuyant sur [qpdf](https://qpdf.sourceforge.io/).

## Prerequis

- Python 3.10+
- `qpdf` installe et disponible dans le PATH :
  - Debian/Ubuntu : `sudo apt install qpdf`
  - macOS : `brew install qpdf`
  - Windows : https://qpdf.sourceforge.io/

## Utilisation

```bash
# Mode interactif (demande le chemin et le mot de passe)
python pdf_unlocker.py

# Mode CLI classique
python pdf_unlocker.py fichier.pdf motdepasse

# Mode drag-and-drop (glissez le fichier dans le terminal, le mot de passe est demande)
python pdf_unlocker.py fichier.pdf

# Mode batch : plusieurs fichiers avec le meme mot de passe
python pdf_unlocker.py fichier1.pdf fichier2.pdf fichier3.pdf motdepasse
```

Le fichier deverrouille est enregistre dans le meme repertoire que l'original, avec le suffixe `_deverrouille` (ex : `fichier.pdf` -> `fichier_deverrouille.pdf`).

## Fonctionnalites

- Validation du fichier d'entree (existence, extension, permissions de lecture) avant traitement.
- Deverrouillage via `qpdf --decrypt`, execute dans un fichier temporaire puis deplace vers la destination finale (les fichiers temporaires sont toujours nettoyes).
- Messages clairs de succes/echec, avec affichage de la taille avant/apres.
- Gestion des erreurs : fichier inexistant, mot de passe incorrect, permissions insuffisantes, qpdf absent du systeme.
- Support du traitement par lot (batch) avec un mot de passe commun.
