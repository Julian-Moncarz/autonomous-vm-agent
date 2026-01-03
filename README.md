# Computer Use VM Agent!

Giving Claude a Debian VM to use in the same manner a humna would (screenshot, move mouse, type, click).

https://github.com/user-attachments/assets/2e2e228c-9ee2-444e-bfa3-b04c2c299110

## Requirements

- macOS with Apple Silicon (ARM64) or Intel
- UTM (free VM software for Mac)
- Python 3.10+
- Anthropic API key

## Quick Start

See **[SETUP.md](SETUP.md)** for detailed first-time setup instructions.

To use once set up: just run python main.py

## How it works

flowchart TB
    subgraph MacHost["Mac Host"]
        main["main.py: Claude API agent loop + CLI"]
        vm["vm.py: SSH connection + xdotool commands"]
    end

    subgraph DebianVM["Debian VM (UTM)"]
        desktop["XFCE Desktop + Firefox + xdotool + scrot"]
    end

    subgraph AgentLoop["Agent Loop"]
        A["1. Claude receives task + screenshot"]
        B["2. Claude decides action\n(move mouse, click, type, etc.)"]
        C["3. Action executed via SSH + xdotool"]
        D["4. New screenshot taken"]
        E["5. Screenshot sent back to Claude"]
        F{"Task complete?"}
        G["Done"]
        H["Pause & ask user\n(CAPTCHAs, credentials)"]
    end

    MacHost -->|"SSH to VM"| DebianVM

    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
    F -->|No| A
    F -->|Yes| G
    B -.->|"Needs help"| H
    H -.-> A

## License

MIT
