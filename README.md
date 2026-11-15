# 77K client

A small, non-commercial custom launcher for **Minecraft: Java Edition**, written in Python with [minecraft-launcher-lib](https://codeberg.org/JakobDev/minecraft-launcher-lib) and a Qt (PySide6) interface. It is made for personal use and a small group of friends.

## Features

- Instances published by the author: the launcher reads a list (`instances.json`) from this repository and shows the available instances. Players pick one and press Play; it is downloaded, installed and updated automatically.
- Downloads the game, the mod loader, the mods and the required Java runtime from their official sources (Mojang and Modrinth) and the modpack file from this repository's releases. No Minecraft files are distributed with this project.
- Minimal UI: each instance is a rounded square with its logo (name on hover); a ⋯ menu offers refresh, open folder and uninstall.
- Account button (shows the Steve head, or your skin's head when signed in with Microsoft): choose between online mode (Microsoft account) and offline mode (username only).
- Settings (gear icon): view the game logs and set the RAM of each instance in GB.
- Only accounts that own Minecraft: Java Edition can sign in with Microsoft.

## How the Microsoft sign-in works

- Public client using the authorization code flow with PKCE and `state`. No client secret is used.
- Redirect URI: `http://localhost`. A temporary local listener on the user's own computer receives the login code.
- Tokens are stored only on the user's computer, in a local JSON file (`~/77K client/config.json`), in plain text.
- There is no backend server. The app does not send data to the author or to any third party.

## Requirements

- Python 3.10 or newer
- `pip install -r requirements.txt` (minecraft-launcher-lib and PySide6)
- Optional: a Minecraft-style font (`.ttf`) in a `fonts/` folder next to `launcher.py`.

## Run

```
python launcher.py
```

## Publishing an instance (for the author)

1. Export your modpack as a `.mrpack` file (for example from the Modrinth App: instance, Export modpack).
2. Create a GitHub Release and attach the `.mrpack` file to it.
3. Add an entry to `instances.json` with the release download URL and bump `version` whenever you publish an update. Optionally add `icon_url` (https PNG shown on the instance square) and `sha256` (hash of the file) so the launcher verifies the download.
4. Commit `instances.json`. Players get the new list when they open the launcher, and the update is installed the next time they press Play.

---

# 77K (español)

Un launcher pequeño y sin fines de lucro para **Minecraft: Java Edition**, hecho en Python con minecraft-launcher-lib y una interfaz Qt (PySide6). Es para uso personal y para un grupo pequeño de amigos.

## Funciones

- Instancias publicadas por el autor: el launcher lee una lista (`instances.json`) de este repositorio y muestra las instancias disponibles. Quien lo use elige una y pulsa Jugar; se descarga, se instala y se actualiza sola.
- Descarga el juego, el mod loader, los mods y Java desde sus fuentes oficiales (Mojang y Modrinth), y el archivo del modpack desde las releases de este repositorio. No se distribuyen archivos de Minecraft.
- Botón Cuenta: permite elegir entre modo online (cuenta de Microsoft) y modo offline (solo nombre de usuario).
- Ajustes (tuerca): ver los logs del juego y cambiar la RAM de cada instancia en GB.
- Solo pueden entrar con Microsoft las cuentas que tengan Minecraft: Java Edition.

## Uso

```
pip install -r requirements.txt
python launcher.py
```

## Publicar una instancia (para el autor)

1. Exporta tu modpack como archivo `.mrpack` (por ejemplo desde Modrinth App: instancia, Exportar modpack).
2. Crea una Release en GitHub y adjunta el `.mrpack`.
3. Agrega una entrada en `instances.json` con la URL de descarga de la release, y sube el número de `version` cada vez que publiques una actualización. Opcional: `sha256` (hash del archivo) para que el launcher verifique la descarga.
4. Haz commit de `instances.json`. Los jugadores reciben la lista nueva al abrir el launcher y la actualización se instala la próxima vez que pulsen Jugar.

Los tokens de sesión se guardan solo en tu computador. No hay servidor propio ni se envían datos a terceros.
