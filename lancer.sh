#!/bin/sh
# Lanceur de la GMAO « Prévo » pour Mac et Linux.
# Usage : ./lancer.sh [options de serveur.py]
# Aucune installation automatique : le script explique quoi faire si Python manque.

# Se placer dans le dossier du script.
cd "$(dirname "$0")" || exit 1

# Cherche python3 puis python, en vérifiant la version >= 3.11.
PYTHON=""
for candidat in python3 python; do
    if command -v "$candidat" >/dev/null 2>&1 &&
       "$candidat" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
        PYTHON="$candidat"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "Python 3.11 ou plus récent est nécessaire, mais il est introuvable." >&2
    echo "Pour l'installer :" >&2
    echo "  - Site officiel : https://www.python.org/downloads/" >&2
    echo "  - Debian/Ubuntu : sudo apt install python3" >&2
    echo "  - macOS (Homebrew) : brew install python" >&2
    echo "Puis relancez ./lancer.sh" >&2
    exit 1
fi

exec "$PYTHON" serveur.py "$@"
