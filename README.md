# DebloatCraft

DebloatCraft est un outil gratuit pour Windows 10/11 et Linux x86-64. Il réunit un scan matériel local en lecture seule, le nettoyage choisi de caches, un inventaire d'applications, des couleurs d'accent, des profils manuels par jeu et un quiz de thème. Les réglages Windows facultatifs et restaurables restent propres à Windows.

## Fonctionnalités

- Scan local CPU, GPU, mémoire, version Windows et espace disque via PowerShell/CIM.
- Moniteur de performances en temps réel: utilisation CPU, mémoire, GPU lorsque le pilote l'expose, espace disque et processus actifs.
- Réglages de capture de jeu, applications en arrière-plan, effets visuels et priorités multimédia. Les valeurs précédentes sont sauvegardées dans `%APPDATA%\DebloatCraft\settings.json` et peuvent être restaurées depuis l'application.
- Nettoyage avec prévisualisation de Temp utilisateur et caches Epic/Steam détectés. Les fichiers verrouillés sont ignorés; la suppression de fichiers ne peut pas être annulée.
- Inventaire des applications Win32; la désinstallation est confiée aux paramètres Windows, sans exécuter de commande silencieuse depuis le registre.
- Couleur d'accent Windows et profils de couleurs par jeu, appliqués manuellement. Aucun changement de couleur automatique au lancement des jeux.
- Quiz de cinq questions pour choisir l'apparence de DebloatCraft.
- Sous Linux: scan local CPU/GPU/mémoire/disques, moniteur de performances, inventaire de paquets dpkg/rpm/pacman et Flatpak, nettoyage manuel de certains caches utilisateur. Aucun réglage système Linux n'est appliqué.

Le scan ne change rien. Aucun gain de FPS ou de latence n'est garanti. Les optimisations sont laissées au choix de la personne; les réglages TCP, les services système et la pagination du noyau ne sont pas modifiés.

## Tester sous Windows

Lance `optimizer.py` avec Python 3.10+, Tkinter et `psutil` sur Windows ou Linux (`python -m pip install psutil`). Pour les modifications HKLM, l'application Windows doit être exécutée comme administrateur. Les fonctions de scan et de personnalisation sont conçues pour rester locales.

## Compiler le .exe

Les workflows `.github/workflows/build-windows.yml` et `.github/workflows/build-linux.yml` compilent les exécutables sur leurs runners respectifs lors d'un push sur `main`/`master` ou sur demande via Actions. Le build Linux nécessite une machine x86-64 avec Tkinter. Pour publier une release téléchargeable, pousse un tag versionné après avoir envoyé le projet sur GitHub:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Les workflows publient `DebloatCraft.exe` (Windows) et `DebloatCraft` (Linux x86-64) dans la GitHub Release et comme artefacts Actions. PyInstaller compile en mode `--onefile`; sous Linux, rends le binaire exécutable avant de le lancer (`chmod +x DebloatCraft`).

## Publier le site

1. Crée un dépôt GitHub et pousse les fichiers du projet sur `main` ou `master`.
2. Dans **Settings > Pages**, choisis **GitHub Actions** comme source de publication.
3. Le workflow `.github/workflows/pages.yml` publie `index.html`, `styles.css`, `app.js` et `optimizer.py` à chaque changement pertinent.
4. Les boutons de téléchargement Windows et Linux pointent vers leurs binaires respectifs dans la dernière release lorsque le site est servi depuis `owner.github.io/repo`.

Ce dossier local n'est actuellement relié à aucun dépôt Git distant; la mise en ligne ne démarrera qu'après création et push du dépôt.