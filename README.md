# Computer Use VM Agent!

Giving Claude a Debian VM to use in the same manner a human would (screenshot, move mouse, type, click).

https://github.com/user-attachments/assets/2e2e228c-9ee2-444e-bfa3-b04c2c299110

## Requirements

- macOS with Apple Silicon (ARM64) or Intel
- UTM (free VM software for Mac)
- Python 3.10+
- Anthropic API key

## Quick Start

See **[SETUP.md](SETUP.md)** for detailed first-time setup instructions.

To use once set up: just run python main.py

Note: you don't need to use UTM - any linux machine you can SSH into should be fine (this means the harness could be easily extended to make something like https://theaidigest.org/village)

## How it works

```mermaid
flowchart TD
    A[Screenshot of VM]:::blue --> B[Claude analyzes & decides which tool to use. For example: move mouse, right click, type etc OR ask for help]:::purple
    B --> C[Execute tool via xdotool]:::green
    C --> A
    B -.-> E[Ask user for help]:::orange
    E -.-> A


    classDef blue fill:#1e90ff,stroke:#1e90ff,color:#fff
    classDef purple fill:#9370db,stroke:#9370db,color:#fff
    classDef green fill:#3cb371,stroke:#3cb371,color:#fff
    classDef orange fill:#ff8c00,stroke:#ff8c00,color:#fff

```

```mermaid
flowchart TB
    subgraph Mac["Mac Host"]
        main["main.py"] --> claude["Claude API"] --> tools["Tool Calls"]
        main --> vm["vm.py"]
    end

    subgraph VM["Debian VM (UTM)"]
        xdotool["xdotool - mouse/keyboard control"]
        scrot["scrot - screenshots"]
        xfce["XFCE - desktop environment"]
    end

    vm -->|SSH| VM
```

## License

MIT
