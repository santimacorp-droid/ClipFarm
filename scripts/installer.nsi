!include "MUI2.nsh"
!include "FileFunc.nsh"

Name "ClipFarm Studio"
OutFile "${OUT_EXE}"
Unicode True
RequestExecutionLevel user
SetCompressor /SOLID lzma

; Definitions
!define PRODUCT_NAME "ClipFarm Studio"
!define PRODUCT_VERSION "${APP_VERSION}"
!define PRODUCT_PUBLISHER "ClipFarm"
!define PRODUCT_WEB_SITE "https://clipfarm.app"
!define PRODUCT_DIR_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\ClipFarm.exe"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"

InstallDir "$LOCALAPPDATA\Programs\ClipFarm Studio"

; UI Settings
!define MUI_ICON "${APP_ICON}"
!define MUI_UNICON "${APP_ICON}"
!define MUI_ABORTWARNING

; Welcome Page
!define MUI_WELCOMEPAGE_TITLE "Welcome to ClipFarm Studio Setup"
!define MUI_WELCOMEPAGE_TEXT "This wizard will install ClipFarm Studio v${PRODUCT_VERSION} on your computer.\r\n\r\nClipFarm Studio is a high-efficiency standalone desktop software for automated viral video clipping, speech-to-text, and vertical video rendering.\r\n\r\nClick Next to continue."
!insertmacro MUI_PAGE_WELCOME

; Directory Selection
!insertmacro MUI_PAGE_DIRECTORY

; Installation Progress
!insertmacro MUI_PAGE_INSTFILES

; Finish Page
!define MUI_FINISHPAGE_RUN "$INSTDIR\Launch_ClipFarm.bat"
!define MUI_FINISHPAGE_RUN_TEXT "Launch ClipFarm Studio"
!insertmacro MUI_PAGE_FINISH

; Uninstaller Pages
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Languages
!insertmacro MUI_LANGUAGE "English"

Section "MainSection" SEC01
  SetOutPath "$INSTDIR"
  SetOverwrite on
  
  File /r "${STAGING_DIR}\*.*"

  ; Create Shortcuts
  CreateDirectory "$SMPROGRAMS\ClipFarm Studio"
  CreateShortcut "$SMPROGRAMS\ClipFarm Studio\ClipFarm Studio.lnk" "$INSTDIR\Launch_ClipFarm.bat" "" "$INSTDIR\app_icon.ico" 0
  CreateShortcut "$SMPROGRAMS\ClipFarm Studio\Uninstall.lnk" "$INSTDIR\uninstall.exe"
  CreateShortcut "$DESKTOP\ClipFarm Studio.lnk" "$INSTDIR\Launch_ClipFarm.bat" "" "$INSTDIR\app_icon.ico" 0

  ; Create Uninstaller
  WriteUninstaller "$INSTDIR\uninstall.exe"

  ; Write Registry Keys for Windows Add/Remove Programs
  WriteRegStr HKCU "${PRODUCT_DIR_REGKEY}" "" "$INSTDIR\Launch_ClipFarm.bat"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "DisplayName" "$(^Name)"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\uninstall.exe"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "DisplayIcon" "$INSTDIR\app_icon.ico"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"
  WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
SectionEnd

Section Uninstall
  RMDir /r "$INSTDIR\backend"
  RMDir /r "$INSTDIR\frontend"
  RMDir /r "$INSTDIR\data"
  RMDir /r "$INSTDIR\output"
  RMDir /r "$INSTDIR\logs"
  Delete "$INSTDIR\*.*"
  RMDir "$INSTDIR"

  Delete "$DESKTOP\ClipFarm Studio.lnk"
  Delete "$SMPROGRAMS\ClipFarm Studio\*.*"
  RMDir "$SMPROGRAMS\ClipFarm Studio"

  DeleteRegKey HKCU "${PRODUCT_UNINST_KEY}"
  DeleteRegKey HKCU "${PRODUCT_DIR_REGKEY}"
SectionEnd
