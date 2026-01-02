# Autonomous VM Agent

Claude controls a Debian VM to complete tasks autonomously.

https://github.com/user-attachments/assets/2e2e228c-9ee2-444e-bfa3-b04c2c299110

## Overview

This system allows Claude to control a virtual machine through mouse movements, clicks, keyboard input, and screenshots. Claude can complete long-horizon tasks like web research, creating documents, and posting to social media.

## Requirements

- macOS with Apple Silicon (ARM64) or Intel
- UTM (free VM software for Mac)
- Python 3.10+
- Anthropic API key

## Quick Start

See **[SETUP.md](SETUP.md)** for detailed first-time setup instructions.

If already set up:

```bash
python3 main.py
```

Enter a task like "Open Firefox and search for cats"

## VM Setup (One-time)

### 1. Install UTM

```bash
brew install --cask utm
```

### 2. Create Debian VM in UTM

- Download [Debian 12 ARM64 ISO](https://cdimage.debian.org/debian-cd/current/arm64/iso-cd/) (or AMD64 for Intel Macs)
- Create VM in UTM: 4GB RAM, 2 cores, 32GB disk, 1280x800 display
- Install Debian with XFCE desktop

### 3. Configure VM (run inside VM)

```bash
# Install required packages
sudo apt update
sudo apt install -y openssh-server xdotool scrot qemu-guest-agent firefox-esr

# Enable services
sudo systemctl enable ssh qemu-guest-agent

# Configure autologin (optional but recommended)
sudo nano /etc/lightdm/lightdm.conf
# Add under [Seat:*]:
# autologin-user=YOUR_USERNAME
```

### 4. Setup SSH key access

```bash
# On Mac host
ssh-copy-id user@VM_IP
```

### 5. Symlink utmctl

```bash
sudo ln -sf /Applications/UTM.app/Contents/MacOS/utmctl /usr/local/bin/utmctl
```

## Usage

```bash
# Auto-detect VM IP
python main.py --vm "Debian-Claude" --ssh-user user

# Or specify IP directly
python main.py --ssh-host 192.168.64.4 --ssh-user user
```

## Example Tasks

**Simple:**
```
Go to https://news.ycombinator.com and tell me the top 3 headlines
```

**Complex:**
```
Find a niche blog about something weird (like competitive duck herding).
Then create a Reddit post citing the blog and asking users what weird niches they've found.
```

## How It Works

1. Claude receives a task and a screenshot of the VM desktop
2. Claude decides what action to take (move mouse, click, type, etc.)
3. The action is executed via SSH + xdotool
4. A new screenshot is taken and sent back to Claude
5. Repeat until task is complete

Claude can also pause and ask the user for help (e.g., solving CAPTCHAs or entering credentials).

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Mac Host                                │
│  main.py: Claude API agent loop + CLI                          │
│  vm.py: SSH connection + xdotool commands                      │
│                              │                                  │
│                         SSH to VM                               │
└──────────────────────────────┼──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Debian VM (UTM)                            │
│  XFCE Desktop + Firefox + xdotool + scrot                      │
└─────────────────────────────────────────────────────────────────┘
```

## License

MIT
