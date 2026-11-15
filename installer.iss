; Instalador de CLIENT77K (Inno Setup). Lo compila el robot de GitHub; la versión llega por /DMyAppVersion.
#ifndef MyAppVersion
  #define MyAppVersion "0.0"
#endif

[Setup]
AppId={{5B1F6C0E-9A47-4D3B-8E21-77A0C4D9E1F3}
AppName=CLIENT77K
AppVersion={#MyAppVersion}
AppVerName=CLIENT77K {#MyAppVersion}
AppPublisher=Tomate77K
AppPublisherURL=https://github.com/Tomate77K/Mi-launcher
DefaultDirName={autopf}\CLIENT77K
DisableProgramGroupPage=yes
; Se instala solo para tu usuario (sin pedir permisos de administrador), así el launcher
; puede actualizarse a sí mismo sin problemas.
PrivilegesRequired=lowest
OutputDir=installer_out
OutputBaseFilename=CLIENT77K-setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\CLIENT77K.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "dist\CLIENT77K.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\CLIENT77K"; Filename: "{app}\CLIENT77K.exe"
Name: "{autodesktop}\CLIENT77K"; Filename: "{app}\CLIENT77K.exe"; Tasks: desktopicon

; Si había una versión anterior llamada «77K client» / client.exe, se limpia al actualizar
[InstallDelete]
Type: files; Name: "{app}\client.exe"
Type: files; Name: "{app}\client.exe.old"
Type: files; Name: "{autoprograms}\77K client.lnk"
Type: files; Name: "{autodesktop}\77K client.lnk"

[Run]
Filename: "{app}\CLIENT77K.exe"; Description: "Abrir CLIENT77K"; Flags: nowait postinstall

[UninstallDelete]
Type: files; Name: "{app}\CLIENT77K.exe.old"
Type: files; Name: "{app}\CLIENT77K.exe.new"
