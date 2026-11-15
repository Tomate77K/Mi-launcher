; Instalador de 77K client (Inno Setup). Lo compila el robot de GitHub; la versión llega por /DMyAppVersion.
#ifndef MyAppVersion
  #define MyAppVersion "0.0"
#endif

[Setup]
AppId={{5B1F6C0E-9A47-4D3B-8E21-77A0C4D9E1F3}
AppName=77K client
AppVersion={#MyAppVersion}
AppVerName=77K client {#MyAppVersion}
AppPublisher=Tomate77K
AppPublisherURL=https://github.com/Tomate77K/Mi-launcher
DefaultDirName={autopf}\77K client
DisableProgramGroupPage=yes
; Se instala solo para tu usuario (sin pedir permisos de administrador), así el launcher
; puede actualizarse a sí mismo sin problemas.
PrivilegesRequired=lowest
OutputDir=installer_out
OutputBaseFilename=77K-client-setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\client.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "dist\client.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\77K client"; Filename: "{app}\client.exe"
Name: "{autodesktop}\77K client"; Filename: "{app}\client.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\client.exe"; Description: "Abrir 77K client"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\client.exe.old"
Type: files; Name: "{app}\client.exe.new"
