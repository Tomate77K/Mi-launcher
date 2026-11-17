# CLIENT77K by TOMATE77K

> **Unofficial, independent project.** CLIENT77K is a third-party launcher made by Tomate77K. It is **not** affiliated with, endorsed or approved by Mojang Studios, Microsoft or Minecraft. "Minecraft" is a trademark of Mojang Studios.
> **Proyecto independiente y no oficial.** CLIENT77K es un launcher de terceros hecho por Tomate77K. **No** está afiliado, respaldado ni aprobado por Mojang Studios, Microsoft ni Minecraft.
> Contact / Contacto: open an [issue](../../issues) in this repository / abre un [issue](../../issues) en este repositorio.

A small, non-commercial custom launcher for **Minecraft: Java Edition**, written in Python with [minecraft-launcher-lib](https://codeberg.org/JakobDev/minecraft-launcher-lib) and a Qt (PySide6) interface. It is made for personal use and a small group of friends.

## Features

- Instances published by the author: the launcher reads a list (`instances.json`) from this repository and shows the available instances. Players pick one and press Play; it is downloaded, installed and updated automatically.
- Downloads the game, the mod loader, the mods and the required Java runtime from their official sources (Mojang and Modrinth) and the modpack file from this repository's releases. No Minecraft files are distributed with this project.
- Minimal UI: each instance is a rounded square with its logo (name on hover); a ⋯ menu offers refresh, open folder and uninstall.
- Account button (shows your skin's head once signed in): sign in or out with your Microsoft account. A Microsoft account that owns Minecraft: Java Edition is required to play; there is no offline or username-only mode.
- Settings (gear icon): view the game logs and set the RAM of each instance in GB.
- Ownership is verified through the normal Microsoft / Xbox / Minecraft sign-in flow. The launcher does not bypass or replace it.

## How the Microsoft sign-in works

- Public client using the authorization code flow with PKCE and `state`. No client secret is used.
- Redirect URI: `http://localhost`. A temporary local listener on the user's own computer receives the login code.
- Tokens are stored only on the user's computer, in a local JSON file (`~/77K client/config.json`), in plain text.
- There is no backend server. The app does not send data to the author or to any third party.

## Requirements

- Python 3.10 or newer
- `pip install -r requirements.txt` (minecraft-launcher-lib and PySide6)
- The `fonts/` folder holds the Poppins font (SIL Open Font License 1.1), used by the interface. Keep the folder next to `launcher.py`.

## Run

```
python launcher.py
```

## Publishing an instance (for the author)

1. Export your modpack as a `.mrpack` file (for example from the Modrinth App: instance, Export modpack).
2. Create a GitHub Release and attach the `.mrpack` file to it.
3. Add an entry to `instances.json` with the release download URL and bump `version` whenever you publish an update. Optionally add `icon_url` (https PNG shown on the instance square) and `sha256` (hash of the file) so the launcher verifies the download.
4. Commit `instances.json`. Players get the new list when they open the launcher, and the update is installed the next time they press Play.

## Launcher updates (for the author)

1. Raise `LAUNCHER_VERSION` in `launcher.py` (and the version in `version_info.txt`) and build with `build_un_solo_exe.bat`.
2. Create a GitHub Release (for example `app-0.8`) and attach the new `client.exe`.
3. Edit `latest.json`: set `version` and the release download `url` (it must start with `https://github.com/Tomate77K/`). Optional: `sha256` of the file.
4. When players open the launcher they are offered the update; it downloads, replaces itself and restarts.

---

# 77K (español)

Un launcher pequeño y sin fines de lucro para **Minecraft: Java Edition**, hecho en Python con minecraft-launcher-lib y una interfaz Qt (PySide6). Es para uso personal y para un grupo pequeño de amigos.

## Funciones

- Instancias publicadas por el autor: el launcher lee una lista (`instances.json`) de este repositorio y muestra las instancias disponibles. Quien lo use elige una y pulsa Jugar; se descarga, se instala y se actualiza sola.
- Descarga el juego, el mod loader, los mods y Java desde sus fuentes oficiales (Mojang y Modrinth), y el archivo del modpack desde las releases de este repositorio. No se distribuyen archivos de Minecraft.
- Botón Cuenta: iniciar o cerrar sesión con tu cuenta de Microsoft. Para jugar hace falta una cuenta con Minecraft: Java Edition; no existe modo offline ni entrar solo con un nombre.
- Ajustes (tuerca): ver los logs del juego y cambiar la RAM de cada instancia en GB.
- La propiedad del juego se verifica con el inicio de sesión normal de Microsoft / Xbox / Minecraft. El launcher no lo evita ni lo reemplaza.

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

## Actualizar el launcher (para el autor)

1. Sube `LAUNCHER_VERSION` en `launcher.py` (y la versión en `version_info.txt`) y compila con `build_un_solo_exe.bat`.
2. Crea una Release en GitHub (por ejemplo `app-0.8`) y adjunta el nuevo `client.exe`.
3. Edita `latest.json`: cambia `version` y la `url` de descarga de la release (debe empezar con `https://github.com/Tomate77K/`). Opcional: `sha256` del archivo.
4. Al abrir el launcher, los jugadores reciben la oferta de actualizar; se descarga, se reemplaza solo y se reinicia.
