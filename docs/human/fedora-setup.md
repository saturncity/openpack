# Move development to the Fedora workstation

One-time, about 20 minutes. Everything the project needs is on GitHub, so nothing is copied from the Mac. Each step is one action; the expected result follows it. Do them in order, in a terminal on Fedora.

## 0. Check the machine type
```
uname -m
```
Expected: `x86_64`. If it prints `aarch64`, stop: the simulator needs an Intel/AMD machine.

## 1. Install system packages (the only step needing your password)
```
sudo dnf install -y git gh cmake ninja-build gperf ccache dfu-util dtc wget xz file python3 python3-pip python3-devel python3-tkinter SDL2-devel glibc-devel.i686 libstdc++-devel.i686 libgcc.i686 fftw-devel.i686 jq curl
```
Expected: ends with `Complete!`. The `.i686` packages let the radio simulator build its 32-bit programs.

## 2. Install Homebrew for Linux (lets agents install tools without your password)
```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
Expected: it prints two or three lines starting with `echo` or `eval` under "Next steps". Copy and run those lines. Then `brew --version` prints a version.

## 3. Sign in to GitHub
```
gh auth login
```
Pick: GitHub.com, HTTPS, Yes (authenticate git), Login with a web browser. Follow the code it shows. Expected: `Logged in as saturncity`.

## 4. Get the project
```
cd ~ && git clone https://github.com/saturncity/openpack.git OpenPack && cd OpenPack
```
Expected: a folder `~/OpenPack` with `CLAUDE.md` in it. The agent settings come with it (`.claude/settings.json`).

## 5. Install Claude Code and sign in
```
curl -fsSL https://claude.ai/install.sh | bash
```
Then open a new terminal, `cd ~/OpenPack`, run `claude`, and follow the login prompt. Expected: the Claude Code prompt appears. Type `/exit`.

## 6. Keep the machine awake
GNOME: Settings → Power → Screen Blank: Never; Automatic Suspend: Off.
Alternatively start the agent with `systemd-inhibit --what=idle:sleep claude` instead of plain `claude`.

## 7. Stop the Mac session
On the Mac, in the running Claude Code session type: `push everything now and stop`. Wait for it to say it has pushed. Then `/exit`. Don't start it again on the Mac.

## 8. Start on Fedora
```
cd ~/OpenPack && systemd-inhibit --what=idle:sleep claude
```
First message:
```
Read docs/agents/MASTER-PROMPT.md and begin. You are now on the Fedora workstation (Linux x86_64): BabbleSim runs natively here. Finish #18/#19 locally before pushing.
```

## Later (Phase 5, when the dev kits arrive)
Plug the kits into Fedora, not the Mac. The agent will ask you once to install the Nordic command-line tools and SEGGER J-Link (two `sudo dnf install` lines it will give you).

## If it didn't work
- `brew: command not found` after step 2: open a new terminal; the "Next steps" lines were not run.
- Step 1 says a `.i686` package is not found: run `sudo dnf install -y glibc-devel.i686 libstdc++-devel.i686` alone and tell the agent `fftw-devel.i686` is missing; it will build FFTW itself.
- `claude` not found after step 5: run `source ~/.bashrc` or open a new terminal.
