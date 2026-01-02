"""Autonomous VM Agent - Claude controls a Debian VM."""
import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path
from anthropic import Anthropic
from vm import VM, VMError

# Load .env file if it exists
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

# Tool definitions for Claude
TOOLS = [
    {
        "name": "screenshot",
        "description": "Take a screenshot of the VM desktop (includes cursor). Use frequently to verify actions.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "move_mouse",
        "description": "Move mouse cursor to absolute screen coordinates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "X coordinate (pixels from left)"},
                "y": {"type": "integer", "description": "Y coordinate (pixels from top)"}
            },
            "required": ["x", "y"]
        }
    },
    {
        "name": "click",
        "description": "Click mouse at current position.",
        "input_schema": {
            "type": "object",
            "properties": {
                "button": {"type": "string", "enum": ["left", "right"], "default": "left"},
                "clicks": {"type": "integer", "default": 1, "description": "1=single, 2=double"}
            },
            "required": []
        }
    },
    {
        "name": "type_text",
        "description": "Type text at cursor. For Enter/Tab/etc, use press_key.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"]
        }
    },
    {
        "name": "press_key",
        "description": "Press key or combo. Examples: Return, Tab, Escape, ctrl+a, alt+F4, Page_Down",
        "input_schema": {
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"]
        }
    },
    {
        "name": "ask_user",
        "description": "Pause and ask user a question (for CAPTCHAs, credentials, decisions).",
        "input_schema": {
            "type": "object",
            "properties": {"question": {"type": "string"}},
            "required": ["question"]
        }
    },
    {
        "name": "wait",
        "description": "Wait for page loads or animations. Max 30 seconds.",
        "input_schema": {
            "type": "object",
            "properties": {"seconds": {"type": "number"}},
            "required": ["seconds"]
        }
    }
]

MAX_ITERATIONS = 100
SCREENSHOT_DIR = Path(__file__).parent / "screenshots"


def execute_tool(vm: VM, name: str, args: dict) -> dict:
    """Execute a tool, return result dict."""
    try:
        if name == "screenshot":
            png = vm.screenshot()
            # Save locally for user to view
            SCREENSHOT_DIR.mkdir(exist_ok=True)
            timestamp = time.strftime("%H%M%S")
            filepath = SCREENSHOT_DIR / f"{timestamp}.png"
            filepath.write_bytes(png)
            print(f"    [{filepath}]")
            return {"success": True, "image": base64.b64encode(png).decode()}
        elif name == "move_mouse":
            vm.move_mouse(args["x"], args["y"])
            return {"success": True, "moved_to": [args["x"], args["y"]]}
        elif name == "click":
            vm.click(args.get("button", "left"), args.get("clicks", 1))
            return {"success": True}
        elif name == "type_text":
            vm.type_text(args["text"])
            return {"success": True, "chars": len(args["text"])}
        elif name == "press_key":
            vm.press_key(args["key"])
            return {"success": True, "key": args["key"]}
        elif name == "ask_user":
            print(f"\n>>> CLAUDE ASKS: {args['question']}")
            response = input(">>> YOUR RESPONSE: ")
            return {"success": True, "user_said": response}
        elif name == "wait":
            secs = max(0, min(args.get("seconds", 1), 30))
            time.sleep(secs)
            return {"success": True, "waited": secs}
        else:
            return {"success": False, "error": f"Unknown tool: {name}"}
    except VMError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {e}"}


def generate_handoff(client: Anthropic, messages: list, task: str) -> str:
    """Generate a handoff summary for the next agent instance."""
    handoff_request = [{
        "role": "user",
        "content": """You've reached the turn limit. Generate a concise HANDOFF SUMMARY for the next agent instance that will continue this task.

Include:
1. ORIGINAL TASK: What the user asked for
2. PROGRESS: What has been accomplished so far
3. CURRENT STATE: Where things stand (what's on screen, what app is open, etc.)
4. NEXT STEPS: What should be done next to continue/complete the task
5. BLOCKERS: Any issues or obstacles encountered

Be specific and actionable. The next agent will receive this summary plus a fresh screenshot."""
    }]

    # Use the existing conversation context
    handoff_messages = messages + handoff_request

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=handoff_messages
    )

    # Extract text from response
    for block in response.content:
        if hasattr(block, "text") and block.text:
            return block.text
    return "No handoff summary generated."


def run_agent(vm: VM, task: str, handoff_context: str = None):
    """Run the agent loop until task complete or max iterations.

    Returns:
        str or None: Handoff context if stopped due to iteration limit, None if task completed.
    """
    client = Anthropic()

    # Take initial screenshot
    print("Taking initial screenshot...")
    try:
        initial_screenshot = vm.screenshot()
    except VMError as e:
        print(f"Error: Could not take screenshot: {e}")
        return None

    # Build the initial prompt
    base_prompt = f"""You are an autonomous agent controlling a Debian Linux desktop.

YOUR TASK: {task}

GUIDELINES:
- Take screenshots frequently to verify your actions worked
- Move mouse to target BEFORE clicking
- Use wait after clicks that trigger page loads
- If you encounter CAPTCHAs, login prompts, or are stuck, use ask_user
- Be methodical: screenshot -> think -> act -> screenshot to verify"""

    if handoff_context:
        initial_text = f"""{base_prompt}

HANDOFF FROM PREVIOUS AGENT SESSION:
{handoff_context}

The screenshot above shows the current desktop. Continue working on the task from where the previous agent left off."""
    else:
        initial_text = f"""{base_prompt}

The screenshot above shows the current desktop. Begin working on the task."""

    messages = [{
        "role": "user",
        "content": [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": base64.b64encode(initial_screenshot).decode()
                }
            },
            {
                "type": "text",
                "text": initial_text
            }
        ]
    }]

    for iteration in range(MAX_ITERATIONS):
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            tools=TOOLS,
            messages=messages
        )

        # Print any text content (Claude's thinking)
        for block in response.content:
            if hasattr(block, "text") and block.text:
                print(f"\n{block.text}")

        # Check if Claude is done
        if response.stop_reason == "end_turn":
            return None  # Task completed, no handoff needed

        # Process tool calls
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            return None  # No more actions, task likely complete

        # Add assistant message
        messages.append({"role": "assistant", "content": response.content})

        # Execute each tool
        tool_results = []
        for tool in tool_uses:
            # Format tool call nicely
            if tool.name == "screenshot":
                print(f"  > screenshot")
            elif tool.input:
                args = ", ".join(f"{k}={v!r}" for k, v in tool.input.items())
                print(f"  > {tool.name}({args})")
            else:
                print(f"  > {tool.name}()")
            result = execute_tool(vm, tool.name, tool.input)

            # Format result for Claude
            if tool.name == "screenshot" and result.get("success"):
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool.id,
                    "content": [{
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": result["image"]
                        }
                    }]
                })
            else:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool.id,
                    "content": json.dumps(result)
                })

        messages.append({"role": "user", "content": tool_results})

    # Hit iteration limit - generate handoff for next agent
    print(f"\nReached {MAX_ITERATIONS} iteration limit. Generating handoff summary...")
    handoff = generate_handoff(client, messages, task)
    print(f"\n--- HANDOFF SUMMARY ---\n{handoff}\n-----------------------")
    return handoff


def main():
    parser = argparse.ArgumentParser(description="Autonomous VM Agent")
    parser.add_argument("--vm", default=os.environ.get("VM_NAME", "Debian-Claude"),
                        help="UTM VM name")
    parser.add_argument("--ssh-host", default=os.environ.get("VM_SSH_HOST"),
                        help="VM SSH host/IP (auto-detected if not set)")
    parser.add_argument("--ssh-user", default=os.environ.get("VM_SSH_USER", "user"),
                        help="VM SSH username")
    parser.add_argument("--ssh-key", default=os.environ.get("VM_SSH_KEY", "~/.ssh/vm_agent_key"),
                        help="SSH private key path")
    parser.add_argument("--task", help="Task to execute (non-interactive mode)")
    parser.add_argument("--keep-screenshots", action="store_true", help="Keep screenshots after exit")
    args = parser.parse_args()

    # Get VM IP if not provided
    ssh_host = args.ssh_host
    if not ssh_host:
        print(f"Getting IP for VM '{args.vm}'...")
        try:
            ssh_host = VM.get_ip(args.vm)
            print(f"  -> {ssh_host}")
        except VMError as e:
            print(f"Error: {e}")
            print("Is the VM running? Try: utmctl start " + args.vm)
            sys.exit(1)

    # Connect to VM
    vm = VM(args.vm, ssh_host, args.ssh_user, args.ssh_key)
    try:
        vm.connect()
        print(f"Connected to {args.ssh_user}@{ssh_host}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    try:
        if args.task:
            # Non-interactive mode: run single task and exit
            print(f"Task: {args.task}\n")
            handoff = run_agent(vm, args.task)
            # Continue with handoff if iteration limit was reached
            while handoff:
                print("\nContinuing with new agent instance...\n")
                handoff = run_agent(vm, args.task, handoff_context=handoff)
        else:
            # Interactive mode
            print("Enter a task (Ctrl+C to quit)\n")
            while True:
                task = input("> ").strip()
                if not task:
                    continue
                print()
                handoff = run_agent(vm, task)
                # Continue with handoff if iteration limit was reached
                while handoff:
                    print("\nContinuing with new agent instance...\n")
                    handoff = run_agent(vm, task, handoff_context=handoff)
    except KeyboardInterrupt:
        print("\nGoodbye!")
    finally:
        vm.disconnect()
        # Clean up screenshots unless --keep-screenshots
        if not args.keep_screenshots and SCREENSHOT_DIR.exists():
            import shutil
            shutil.rmtree(SCREENSHOT_DIR)
            print("Screenshots cleaned up.")


if __name__ == "__main__":
    main()
