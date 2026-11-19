[Setup]
AppName=Bowman-Morton Pricing Tool Suite
AppVersion=1.0.0
DefaultDirName={autopf}\Bowman-Morton Pricing Suite
DefaultGroupName=Bowman-Morton Manufacturing
UninstallDisplayIcon={app}\BowmanMortonPricingSuite.exe
Compression=lzma2
SolidCompression=yes
OutputDir=.
OutputBaseFilename=Bowman_Morton_Setup_v1.0.0
SetupIconFile=C:\Bowman_Morton_Pricing_Suite\app_logo.ico
WizardSmallImageFile=C:\Bowman_Morton_Pricing_Suite\sidebar_logo.bmp

[Files]
Source: "C:\Bowman_Morton_Pricing_Suite\dist\BowmanMortonPricingSuite\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\Bowman-Morton Pricing Suite"; Filename: "{app}\BowmanMortonPricingSuite.exe"; WorkingDir: "{app}"; IconFilename: "{app}\BowmanMortonPricingSuite.exe"; IconIndex: 0
Name: "{autoprograms}\Bowman-Morton Pricing Suite"; Filename: "{app}\BowmanMortonPricingSuite.exe"; WorkingDir: "{app}"; IconFilename: "{app}\BowmanMortonPricingSuite.exe"; IconIndex: 0
