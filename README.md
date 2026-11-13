# MiLauncher

A small, non-commercial custom launcher for **Minecraft: Java Edition**, written in Python with [minecraft-launcher-lib](https://codeberg.org/JakobDev/minecraft-launcher-lib) and a Tkinter interface. It is made for personal use and a small group of friends.

## Features

- Multiple profiles: each one has its own Minecraft version, RAM setting, extra JVM arguments and game folder (worlds, mods, settings).
- Downloads the selected version, libraries, assets and the required Java runtime from Mojang's official servers. No Minecraft files are distributed with this project.
- Offline mode (username only) for singleplayer, LAN and offline servers.
- Sign in with a Microsoft account to play on regular servers. Only accounts that own Minecraft: Java Edition can sign in.

## How the Microsoft sign-in works

- Public client using the authorization code flow with PKCE and `state`. No client secret is used.
- Redirect URI: `http://localhost`. A temporary local listener on the user's own computer receives the login code.
- Tokens are stored only on the user's computer, in a local JSON file (`~/.mi_launcher/config.json`), in plain text.
- There is no backend server. The app does not send data to the author or to any third party.

## Requirements

- Python 3.10 or newer (with Tkinter)
- `pip install -r requirements.txt`

## Run

```
python launcher.py
```

---

# MiLauncher (español)

Un launcher pequeño y sin fines de lucro para **Minecraft: Java Edition**, hecho en Python con minecraft-launcher-lib y Tkinter. Es para uso personal y para un grupo pequeño de amigos.

## Funciones

- Perfiles múltiples: cada uno con su versión, RAM, argumentos JVM y carpeta de juego propios.
- Descarga la versión, librerías, assets y Java desde los servidores oficiales de Mojang. No se distribuyen archivos de Minecraft.
- Modo offline (solo nombre de usuario) para un jugador, LAN y servidores offline.
- Inicio de sesión con cuenta Microsoft. Solo pueden entrar cuentas que tengan Minecraft: Java Edition.

## Uso

```
pip install -r requirements.txt
python launcher.py
```

Los tokens de sesión se guardan solo en tu computador. No hay servidor propio ni se envían datos a terceros.
