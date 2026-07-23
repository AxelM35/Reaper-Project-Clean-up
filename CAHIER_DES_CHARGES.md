# Cahier des charges — Reaper Project Cleaner

> **Note méthodologique** : ce document a été reconstitué a posteriori par rétro-ingénierie du code source (`reaper_cleaner.py`), du `README.md` et du pipeline CI (`.github/workflows/build.yml`). Il n'existait aucune spécification formelle avant ce document. Il décrit fidèlement le comportement actuel du logiciel, puis propose une analyse des limites et des recommandations.

## 1. Présentation générale

| | |
|---|---|
| **Nom** | Reaper Project Cleaner (titre de fenêtre : *"Reaper Project Cleaner - Clean and Archive Unused Audio Files"*) |
| **Type** | Application de bureau, interface graphique (GUI) |
| **Langage / framework** | Python 3.12, `customtkinter` (surcouche thémée de Tkinter) |
| **Statut** | **Prototype**, explicitement signalé par l'auteur comme non prêt pour un usage réel |
| **Origine** | Portage Python d'un outil initialement écrit en JavaScript par un tiers ("GriffinSauce"), avec ajout de fonctionnalités |
| **Public cible** | Utilisateurs du logiciel audio REAPER (musiciens, ingénieurs du son) souhaitant nettoyer les fichiers audio inutilisés de leurs projets |
| **Distribution** | Exécutables autonomes générés via PyInstaller (`--onefile`) pour Windows, Linux et macOS, produits par CI GitHub Actions |

## 2. Objectif fonctionnel

Permettre à un utilisateur de **retrouver et archiver les fichiers audio qui ne sont plus référencés par aucun projet REAPER** dans un dossier donné, afin de libérer de l'espace disque, sans supprimer définitivement les données (les fichiers sont déplacés, pas effacés).

## 3. Périmètre fonctionnel détaillé

L'application impose un flux de travail linéaire en trois étapes, matérialisé par trois boutons qui s'activent progressivement.

### 3.1. Étape 1 — Scan du dossier (`scan_folder`)

- L'utilisateur sélectionne un dossier racine via un sélecteur natif (`filedialog.askdirectory`).
- L'application parcourt récursivement (`os.walk`) l'arborescence à la recherche de tous les fichiers se terminant par `.rpp` ou `.rpp-bak` (insensible à la casse).
- Pour chaque projet trouvé, sont enregistrés : chemin complet, nom de fichier, taille (en Mo), date de dernière modification (`AAAA-MM-JJ`), et un état de sélection (case cochée par défaut).
- Résultat affiché dans le panneau gauche **"PROJECTS FOUND"**, une ligne par projet (case à cocher + nom + taille), triable par nom ou par taille.
- La barre de statut affiche le nombre de projets trouvés.
- Active le bouton **"2. FIND UNUSED"**.

### 3.2. Étape 2 — Détection des fichiers inutilisés (`find_unused_logic`)

Algorithme en deux phases :

**Phase A — Extraction des références audio dans les projets.**
Pour **chaque** projet trouvé à l'étape 1 (indépendamment de sa sélection) :
- Le fichier `.rpp`/`.rpp-bak` est lu comme texte brut (UTF-8, erreurs ignorées).
- Toutes les occurrences du motif `FILE "..."` sont extraites par expression régulière (`re.findall(r'FILE "(.*?)"', content)`) — c'est la syntaxe utilisée par REAPER dans son format de projet texte pour référencer un média.
- Pour chaque référence trouvée, les séparateurs de chemin sont normalisés, puis :
  - **Chemin absolu** : si le chemin existe sur le disque, il est ajouté (normalisé, en minuscules) à l'ensemble `specific_used_paths`.
  - **Chemin relatif** : résolu par rapport au dossier du projet ; s'il existe, il est ajouté de la même façon.
  - **Chemin non résolu** (ex. fichier situé dans un chemin de recherche global REAPER inconnu de l'outil) : seul le **nom de fichier** (sans le chemin) est ajouté à un ensemble de secours `fallback_safe_names`, par précaution, pour éviter de considérer à tort ce fichier comme inutilisé.

**Phase B — Comparaison avec le disque.**
Pour chaque projet **coché** par l'utilisateur :
- Le dossier du projet est parcouru récursivement à la recherche de fichiers dont l'extension appartient à `AUDIO_EXTENSIONS = ('.wav', '.aif', '.aiff', '.mp3', '.ogg', '.flac', '.mid')`.
- Un fichier est considéré **inutilisé** seulement si :
  1. son chemin normalisé n'est **pas** dans `specific_used_paths`, **et**
  2. son nom de fichier n'est **pas** dans `fallback_safe_names`.
- Les fichiers inutilisés sont dédupliqués par chemin complet.

Résultat affiché dans le panneau droit **"UNUSED FILES"** (texte teinté de rouge), une ligne par fichier (case à cocher + nom + projet d'origine + taille), triable par taille. La barre de statut affiche le nombre de fichiers inutilisés trouvés. Active le bouton **"3. ARCHIVE SELECTED"**.

### 3.3. Étape 3 — Archivage (`archive_files_logic`)

- Seuls les fichiers **cochés** dans la liste des inutilisés sont concernés.
- Une boîte de dialogue de confirmation (`messagebox.askyesno`) demande validation avant toute action.
- Un dossier maître `_Reaper_Cleanup_Archive` est créé (s'il n'existe pas) à la racine du dossier scanné.
- Pour chaque fichier à archiver, un sous-dossier nommé d'après le projet d'origine (nom du `.rpp` sans extension) est créé sous le dossier maître, et le fichier y est **déplacé** (`shutil.move`, jamais supprimé).
- Chaque déplacement est protégé individuellement par un `try/except` : succès et erreurs sont comptabilisés séparément.
- Après archivage, l'analyse (étape 2) est **relancée automatiquement** pour rafraîchir la liste.
- Un résumé (`messagebox.showinfo`) indique le nombre de fichiers archivés, le nombre d'erreurs et l'emplacement du dossier d'archive.

### 3.4. Tri

- Projets : tri par nom (alphabétique) ou par taille (décroissante) — boutons **"Sort Name"** / **"Sort Size"** au-dessus du panneau gauche.
- Fichiers inutilisés : tri par taille (décroissante) — bouton **"Sort Size"** au-dessus du panneau droit.
- Le tri déclenche un simple re-rendu de la liste concernée (aucune donnée n'est recalculée).

## 4. Interface utilisateur

- Fenêtre unique, taille fixe à l'ouverture 1200×800, thème sombre (`Dark`), palette d'accent bleue.
- **En-tête** : champ de saisie affichant le chemin sélectionné (lecture après sélection, pas de saisie manuelle validée) + bouton **"1. SCAN FOLDER"**.
- **Deux colonnes** :
  - Gauche : "PROJECTS FOUND" avec liste déroulante des projets détectés.
  - Droite : "UNUSED FILES" (titre en rouge) avec liste déroulante des fichiers détectés comme inutilisés.
- **Pied de page** : étiquette de statut (texte gris, ex. "Ready", "Found N project files.", "Analyzing for unused audio files...", "Analysis Complete. Found N unused files.") + boutons "2. FIND UNUSED" et "3. ARCHIVE SELECTED" (désactivés tant que l'étape précédente n'a pas été exécutée).
- Aucune barre de menu, aucun raccourci clavier, aucune fenêtre de préférences.

## 5. Exigences non fonctionnelles reconstituées

- **Plateformes** : Windows, Linux, macOS — un exécutable autonome par OS (`ReaperCleaner_Win`, `ReaperCleaner_Linux`, `ReaperCleaner_Mac`), généré par PyInstaller en mode `--onefile --noconsole` via une matrice GitHub Actions (`windows-latest`, `ubuntu-latest`, `macos-latest`).
- **Dépendances** : une seule dépendance tierce, `customtkinter` (`requirements.txt`). Le reste s'appuie uniquement sur la bibliothèque standard Python (`os`, `shutil`, `re`, `datetime`, `tkinter.filedialog`, `tkinter.messagebox`).
- **Réseau / API / base de données** : aucun. L'application ne communique avec aucun service externe et n'a pas de persistance au-delà du système de fichiers local.
- **Persistance de configuration** : aucune. Chaque session démarre sans mémoriser le dernier dossier utilisé ni aucune préférence.
- **Intégration REAPER** : aucune. Pas de SDK REAPER, pas de ReaScript, pas de communication avec une instance de REAPER en cours d'exécution — uniquement lecture du format texte `.rpp`/`.rpp-bak` sur disque.

## 6. Contraintes techniques et format de données

- Le format de projet REAPER (`.rpp`) est traité comme un **fichier texte brut**, analysé par une expression régulière unique (`FILE "(.*?)"`), et non par un analyseur syntaxique structuré du format de chunks RPP.
- Les extensions audio reconnues sont **codées en dur** : `.wav`, `.aif`, `.aiff`, `.mp3`, `.ogg`, `.flac`, `.mid`.
- Le thème d'apparence (`Dark` / `blue`) est fixé au niveau du module, non configurable depuis l'interface.

## 7. Limites et risques identifiés

Cette section reflète une analyse critique du code, au-delà de sa simple description.

1. **Fragilité du parsing regex** — `FILE "(.*?)"` suppose une syntaxe RPP stable et sans variation (guillemets échappés, retours à la ligne dans le chemin, évolutions futures du format REAPER). Toute variante non anticipée peut faire échouer la détection sans avertissement explicite à l'utilisateur.
2. **Statut prototype assumé par l'auteur** — le `README.md` indique explicitement *"THIS IS A PROTOTYPE. DO NOT USE IT IN A REAL CASE SCENARIO."* Il n'existe aucun test automatisé (aucun répertoire de tests dans le dépôt), aucune validation formelle avant que l'outil ne déplace des fichiers audio réels de l'utilisateur.
3. **Risque résiduel de perte de données malgré le déplacement (et non la suppression)** — le mécanisme de "filet de sécurité" par nom de fichier (`fallback_safe_names`) réduit mais n'élimine pas le risque de faux positifs (un fichier réellement utilisé, référencé via un chemin non résolu par l'outil, portant un nom identique à un fichier réellement inutilisé ailleurs, pourrait être classé à tort). À l'inverse, ce même filet peut aussi produire des faux négatifs (un fichier réellement inutilisé mais partageant son nom avec un fichier utilisé ailleurs ne sera jamais proposé à l'archivage).
4. **Pas de gestion des chemins de recherche globaux REAPER** ("media search paths" configurés dans REAPER, en dehors du dossier du projet) — l'outil ne les connaît pas, d'où le recours au filet de sécurité par nom, qui reste une approximation.
5. **Absence d'annulation / historique** — aucune fonction "annuler le dernier archivage", aucun journal persistant des actions effectuées (seuls des `print()` sont émis en console, non stockés).
6. **Portée du scan à l'étape 2 dépendante de la sélection de l'étape 1** — le parsing des références (Phase A) porte sur *tous* les projets trouvés au scan, mais la recherche de fichiers inutilisés (Phase B) ne parcourt que les dossiers des projets **cochés**. Un projet décoché par erreur peut donc laisser des fichiers réellement utilisés hors du calcul de comparaison sans que l'utilisateur en soit averti autrement que par la case décochée elle-même.
7. **Pas de gestion multilingue ni d'accessibilité** — interface en anglais uniquement, pas de support lecteur d'écran signalé, thème sombre non désactivable.
8. **Fenêtre de taille fixe à l'ouverture** — bien que redimensionnable par l'utilisateur (comportement par défaut de Tkinter), aucune adaptation particulière n'est prévue pour petits écrans.

## 8. Recommandations d'amélioration

1. **Ajouter une suite de tests automatisés**, notamment des tests unitaires du parsing RPP couvrant des cas réels variés (chemins absolus/relatifs, caractères spéciaux, formats de versions différentes de REAPER), en s'appuyant sur des fixtures de projets `.rpp` représentatives.
2. **Remplacer le parsing regex par un analyseur structuré** du format de chunks RPP (ou au minimum documenter et durcir la regex actuelle contre les cas limites connus).
3. **Journaliser les actions d'archivage** dans un fichier persistant (horodatage, chemin source, chemin destination, statut), pour audit et pour permettre une restauration manuelle en cas d'erreur.
4. **Ajouter une fonction d'annulation** du dernier archivage (déplacement inverse à partir du journal).
5. **Rendre configurables les extensions audio surveillées**, plutôt que de les figer dans le code.
6. **Prendre en charge les chemins de recherche globaux REAPER**, si accessibles (fichier de configuration REAPER), afin de réduire la dépendance au filet de sécurité par nom de fichier.
7. **Avertir explicitement l'utilisateur**, dans l'interface, lorsque le filet de sécurité par nom de fichier a été utilisé pour un fichier donné (transparence sur l'incertitude de la détection).
8. **Ajouter une internationalisation minimale** et vérifier la compatibilité avec les lecteurs d'écran si l'outil est destiné à un usage plus large.

## 9. Annexe — Inventaire des fichiers du dépôt

| Fichier | Rôle |
|---|---|
| `reaper_cleaner.py` | Application complète (classe `App`, 291 lignes) : interface graphique et logique métier (scan, détection, archivage, tri). |
| `requirements.txt` | Dépendance unique : `customtkinter`. |
| `.github/workflows/build.yml` | Pipeline CI GitHub Actions : construit un exécutable PyInstaller par OS (Windows, Linux, macOS) à chaque push/PR sur `main`/`master`, publié comme artefact de build. |
| `README.md` | Présentation informelle du projet, crédit à l'auteur original (GriffinSauce), avertissement "prototype". |
| `.gitignore` | Exclut notamment les dossiers de projets REAPER de test (`CleanUpSampleProjects/...`) et les artefacts de build PyInstaller (`build/`, `dist/`, `*.spec`) — non versionnés. |
