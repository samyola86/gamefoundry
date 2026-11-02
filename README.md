# Game Foundry

A local Windows dashboard and Python harness connecting **Blender, Unreal Engine, C++ build tools and Ollama**. Create a separate home for each game, open its tools, inspect the architecture and test the pipeline before starting development.

**Game Foundry creates blank projects and runs predefined automation. It is not an autonomous game generator.** Use your main coding assistant for implementation. Local Qwen is a supporting chat model; automatic delegation to it is not implemented.

## New PC: quick start

### 1. Get the source

Download this repository as a ZIP and extract it, or clone it:

```powershell
git clone https://github.com/samyola86/gamefoundry.git
cd gamefoundry
```

Use a local, writable directory. A short location such as `C:\Dev\gamefoundry` is convenient. The repository does not include game assets, models, credentials, the Unreal Engine or a prebuilt Python environment.

### 2. Install the prerequisites

You need Windows 11 x64, WinGet (Microsoft App Installer), internet access and enough free disk space for Unreal, compilers, the model and test builds. Some installations request administrator approval. The complete GPU/runtime test requires an unlocked interactive Windows desktop and a working graphics driver.

From PowerShell in the extracted repository, preview the installer:

```powershell
.\Install-Prerequisites.ps1 -InstallTools -InstallBuildTools -DownloadModel -WhatIf
```

Then install:

```powershell
.\Install-Prerequisites.ps1 -InstallTools -InstallBuildTools -DownloadModel
```

| Component | Setup behavior |
| --- | --- |
| Python 3.11 | Installed through WinGet; no third-party Python packages needed |
| Blender | Pins 5.2.3, the tested profile |
| VS Code | Installs the editor; Codex sign-in is separate |
| Ollama | Installs the service; downloads `qwen2.5-coder:7b` only with `-DownloadModel` |
| Build Tools | Pins Visual Studio Build Tools 2022 17.14.44; requests MSVC x64/x86 tools and Windows SDK 26100 |
| Epic Games Launcher | Installs the launcher, **not Unreal Engine itself** |

You can run the three switches separately. The script does not trigger a restart. Respect any installer restart requirement before testing. Versions are pinned for reproducibility; if a pinned package is removed from the WinGet catalog, the script stops rather than silently selecting a different version. Review the failure and use an official installer, or update the pinned profile deliberately.

Existing Build Tools installations may be skipped by WinGet even when required components are missing. Open Visual Studio Installer and modify Build Tools to add **MSVC v143 x64/x86 tools** and **Windows 11 SDK 10.0.26100**. The full C++ check is the final authority.

If PowerShell blocks local scripts, follow your device's script policy or install the listed packages manually. This project does not bypass security policies. Do not run random internet bootstrap commands.

### 3. Install Unreal through Epic

Open Epic Games Launcher, sign in, review Epic's terms and install **Unreal Engine 5.8**. The original machine tested **5.8.4**. Keep the Win64 editor and build/cook tools installed.

This step is intentionally manual: Game Foundry does not handle Epic credentials, accept Epic agreements for you, download protected engine distributions or redistribute Unreal. Custom engine locations can be entered in Settings if discovery misses them.

Epic documents compatible compilers and SDKs in its [UE 5.8 Visual Studio setup guide](https://dev.epicgames.com/documentation/en-us/unreal-engine/setting-up-visual-studio-development-environment-for-cplusplus-projects-in-unreal-engine). This profile uses the supported VS 2022 toolchain and SDK 26100; the full Visual Studio IDE is not needed to keep VS Code as your editor.

### 4. Set up and open Game Foundry

Open a **fresh terminal** after installations, then double-click:

1. **`setup.cmd`** — creates this checkout's `.venv`, detects tools and creates initial per-PC settings.
2. **`Start-GameFoundry.cmd`** — starts the local background server and opens the dashboard.

Default URL: **http://127.0.0.1:8787**.

Setup can be repeated: it keeps existing settings and projects. No pip packages are installed. To run setup with an explicit Python interpreter instead, use `python bootstrap.py` with Python 3.11 or newer.

In **Settings**, review these values before running tests:

- Default games folder.
- Blender `blender.exe`.
- Unreal `UnrealEditor.exe` under `Engine\Binaries\Win64`.
- VS Code `Code.exe`.
- Python: this repository's `.venv\Scripts\python.exe`.
- Local Ollama URL and installed model name.

Discovery searches standard install locations and the Unreal 5.8 registry entry. Missing tools stay blank; saving a path does not claim the tool works. For custom installations, enter the full executable paths manually. The current project templates target Unreal **5.8**; changing the engine path does not automatically port the templates to another engine version.

### 5. Verify the whole pipeline

Create a sample game, open **Architecture**, select it and click **Test whole pipeline**. It runs:

1. Python error-exit and timeout handling.
2. Headless Blender mesh generation and FBX export.
3. Unreal Python import, actor placement and map save.
4. A separate Unreal process reopening the saved scene.
5. Exact-response inference using the selected local model.
6. GPU editor screenshot and simulation-world checks.
7. A real minimal Unreal C++ compile and link.
8. Windows content-only cooking, packaging and archive.
9. Launch of the packaged smoke-test game and map.

Lines turn **green only for passing checks**, amber while running, red on failure and gray when untested. Changes to tool settings invalidate the diagram's claims for older settings. Retry preserves successful stages/receipts and reruns failed stages; original failure evidence is retained. Tests use independent projects and do not validate or modify your selected game's actual content, gameplay or plugins.

The full check takes several minutes and writes sizable build artifacts. It may open temporary Unreal editor/game windows. Run one test at a time. Do not edit the test projects or shut down the dashboard while a test is active.

## Reuse with different games

The new-game dialog offers **Windows** and **Android**. Choosing Android records the selection in `game.json` and the dashboard library, and sets `TargetPlatforms: ["Android"]` in the new Unreal project descriptor. This selects the project's intended platform; it does not install the Android SDK/NDK, set up signing or produce an APK/AAB. Configure the Android tools required by your Unreal version before packaging. Existing full-pipeline checks remain **Windows toolchain tests**, including when associated with an Android game; they do not certify Android builds.

- **New game:** choose its name and parent folder. Creates a new directory with a blank Unreal project, Blender file, VS Code workspace, `game.json`, Assets, Builds and Notes. Existing folders are never overwritten.
- **Register existing project:** provide its `.uproject` path. Stores a reference without editing project files.
- **Blender:** opens `Assets/<GameName>.blend` for dashboard-created games, creating a missing starter file without overwriting existing work. For read-only registered projects, opens Blender without writing a file.
- **Ollama / Qwen:** opens local project chat. History stays in the app's data directory. Qwen receives the project name, target and recent messages; it does not automatically read project files, run tools or edit code.
- **VS Code / Unreal:** launch the selected project's tools. Saving manually inside those apps can change the project.

Global tool settings are shared across games. Per-game engine/tool overrides, game-specific builds, gameplay tests and automatic planning/repair are not implemented. The full test builds a **smoke-test game**, not the selected real game.

For coding-assistant work, open `GameFoundry.code-workspace`, install the Codex extension if desired and sign in yourself. VS Code may ask you to review workspace trust before enabling tasks. Neither authentication nor workspace trust is automated. See the [official Codex IDE guide](https://learn.chatgpt.com/docs/ide).

## Diagnostics and troubleshooting

```powershell
.\.venv\Scripts\python.exe doctor.py --json
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Doctor reports detected files, Blender version, Unreal build metadata, SDK headers and Ollama/model availability. **It does not replace executable pipeline tests.** Its return code can be nonzero when a prerequisite is missing; it does not claim C++ compilation succeeded just because SDK headers exist.

| Symptom | Next check |
| --- | --- |
| Missing paths | Review Settings; custom drive installations may need manual paths |
| Ollama unreachable | Open Ollama or run `ollama serve`; default address is `http://127.0.0.1:11434` |
| Model not found | Run `ollama pull qwen2.5-coder:7b`, or choose an installed model in Settings |
| No loaded model | Normal when idle; Architecture reports actual loaded models separately from the configured model |
| SDK/compiler failure | Modify Build Tools to install the requested MSVC and Windows SDK components; retry the C++ check |
| GPU/simulation failure | Read the stage log, check graphics drivers and available memory, and run from an unlocked interactive desktop |
| Port occupied | Stop the other checkout, or set `GAME_DASHBOARD_PORT` to another port before launching |
| Moved checkout | Rerun setup; update the Python path in Settings if an existing configuration still points at the old checkout |

Each run has stdout/stderr logs, engine logs, JSON receipts and stage timeouts. Process timeouts do not guarantee cleanup of every descendant helper process. A restart labels unfinished jobs as interrupted; it does not assume they completed. Do not start another server process against the same app data directory while a test runs.

## Data locations and updates

| Location | Contents |
| --- | --- |
| Repository folder | Source, templates, launch/setup scripts and local `.venv` |
| `%LOCALAPPDATA%\GameFoundry\data` | Settings, project registrations, chat histories and run index |
| `%LOCALAPPDATA%\GameFoundry\runs` | Isolated projects, screenshots, builds, receipts and logs |
| `%LOCALAPPDATA%\GFBuilds\<run-id>` | Short-path C++ build staging to avoid Windows path-length limits |
| `Documents\GameFoundryGames` | Default location for new games; configurable |

No runtime data or environment is committed. Updating the source with `git pull` does not overwrite your per-PC settings or game folders. Review settings after changing installed tool versions. Data is not automatically backed up or cleaned up.

Optional environment overrides:

```powershell
$env:GAMEFOUNDRY_HOME = 'D:\GameFoundryData'
$env:GAMEFOUNDRY_BUILD_ROOT = 'D:\GFBuilds'
$env:GAME_DASHBOARD_PORT = '8788'
.\Start-GameFoundry.cmd
```

Choose writable absolute paths; keep the compiler build root short. Use the same overrides when running setup, launch and diagnostics. The dashboard binds only to loopback and does not upload to a cloud service. State-changing requests require a session token and host/origin checks. It is a personal local app, not a hardened network or multi-user service. Treat local chat/log files as private.

Closing the browser leaves the background dashboard running. To stop it, end only the Python process whose command line points to this checkout's `server.py`; don't terminate unrelated Python processes. There is no Windows auto-start service.

## Repository layout

```text
server.py                 Local API, project library, chat and job queue
index.html                Dashboard, settings, activity and architecture
config.py                 Per-PC paths and tool discovery
bootstrap.py              Local Python environment and initial settings
doctor.py                 Read-only prerequisite report
launch.py                 Background server launcher
Install-Prerequisites.ps1  Optional official-package installer
templates/                Blender/Unreal scripts and minimal C++ source
tests/                    Host-independent behavior tests
.github/workflows/         Source/unit checks on Windows
```

Unreal, Blender, Ollama, Qwen weights and Microsoft tools are external prerequisites with their own licenses. They are not bundled here.

## Verification scope

The original local pipeline passed Blender 5.2.3, Unreal 5.8.4, MSVC 14.44, SDK 26100, GPU/simulation, Windows package/runtime and Qwen inference checks on a Windows 11 machine with an RTX 3060 12 GB and about 24 GB usable RAM. This is an observed configuration, not a minimum hardware specification.

The portable packaging is checked separately using a clean configuration and independent test directory on that machine. A complete fresh-Windows installation has **not** been validated in a clean VM. CI tests source/configuration behavior; it does not include Unreal, a GPU or Qwen and must not be interpreted as a full integration pass.

Installer references: [Microsoft WinGet install](https://learn.microsoft.com/en-us/windows/package-manager/winget/install), [Microsoft Build Tools component IDs](https://learn.microsoft.com/en-us/visualstudio/install/workload-component-id-vs-build-tools), [Epic UE compiler setup](https://dev.epicgames.com/documentation/en-us/unreal-engine/setting-up-visual-studio-development-environment-for-cplusplus-projects-in-unreal-engine).
