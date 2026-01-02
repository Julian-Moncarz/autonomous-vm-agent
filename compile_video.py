#!/usr/bin/env python3
"""Compile a session log into a video with action/reasoning overlays."""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from session_recorder import SessionRecorder

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def add_overlay(screenshot_path: str, actions: list[str], reasoning: Optional[str]) -> Image.Image:
    """Add action and reasoning overlay to a screenshot."""
    img = Image.open(screenshot_path).convert("RGB")
    width, height = img.size

    # Overlay is 1/4 of image height
    overlay_height = height // 4
    # Ensure total height is even for h264 compatibility
    total_height = height + overlay_height
    if total_height % 2 == 1:
        overlay_height += 1

    # Create new image with overlay space
    new_img = Image.new("RGB", (width, height + overlay_height), color=(30, 30, 30))
    new_img.paste(img, (0, 0))

    draw = ImageDraw.Draw(new_img)

    # Try to get a nice font - bigger sizes
    font_large = font_small = None
    for font_path in [
        "/System/Library/Fonts/SFNSMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ]:
        try:
            font_large = ImageFont.truetype(font_path, 22)
            font_small = ImageFont.truetype(font_path, 18)
            break
        except (OSError, IOError):
            continue

    if not font_large:
        font_large = font_small = ImageFont.load_default()

    y_pos = height + 15
    padding = 20
    line_height_large = 30
    line_height_small = 26

    # Draw actions
    if actions:
        action_text = "▶ " + " → ".join(actions)
        # Truncate if too long
        max_chars = (width - 2 * padding) // 11
        if len(action_text) > max_chars:
            action_text = action_text[:max_chars - 3] + "..."
        draw.text((padding, y_pos), action_text, fill=(100, 255, 100), font=font_large)
        y_pos += line_height_large + 5

    # Draw reasoning (word-wrapped)
    if reasoning:
        reasoning = " ".join(reasoning.split())  # Normalize whitespace
        chars_per_line = max(1, (width - 2 * padding) // 11)
        words = reasoning.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            if current_length + len(word) + 1 <= chars_per_line:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_length = len(word)
        if current_line:
            lines.append(" ".join(current_line))

        # Calculate max lines that fit
        remaining_height = (height + overlay_height) - y_pos - 10
        max_lines = max(1, remaining_height // line_height_small)

        for line in lines[:max_lines]:
            draw.text((padding, y_pos), line, fill=(200, 200, 200), font=font_small)
            y_pos += line_height_small
        if len(lines) > max_lines:
            draw.text((padding, y_pos - line_height_small), "...", fill=(150, 150, 150), font=font_small)

    return new_img


def compile_video(log_path: str, output_path: str, fps: float = 0.5) -> bool:
    """Compile session log into video.

    Args:
        log_path: Path to session log JSON
        output_path: Path for output video
        fps: Frames per second

    Returns:
        True if successful
    """
    if not HAS_PIL:
        print("Error: Pillow not installed. Run: pip install Pillow")
        return False

    # Check ffmpeg
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: ffmpeg not found. Install with: brew install ffmpeg")
        return False

    # Load log
    print(f"Loading {log_path}...")
    recorder = SessionRecorder.load_log(log_path)

    if not recorder.frames:
        print("No frames in log")
        return False

    print(f"Compiling {len(recorder.frames)} frames to {output_path}...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Process each frame
        for i, frame in enumerate(recorder.frames):
            if not Path(frame.screenshot_path).exists():
                print(f"Warning: Screenshot not found: {frame.screenshot_path}")
                continue

            annotated = add_overlay(frame.screenshot_path, frame.actions, frame.reasoning)
            frame_path = tmpdir / f"frame_{i:05d}.png"
            annotated.save(frame_path)

        # Run ffmpeg
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", str(tmpdir / "frame_%05d.png"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", "23",
            output_path
        ]

        result = subprocess.run(ffmpeg_cmd, capture_output=True)
        if result.returncode != 0:
            print(f"ffmpeg error: {result.stderr.decode()}")
            return False

    print(f"Video saved to {output_path}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Compile session log to video")
    parser.add_argument("log", help="Session log JSON file")
    parser.add_argument("-o", "--output", required=True, help="Output video file (e.g., session.mp4)")
    parser.add_argument("--fps", type=float, default=0.5, help="Frames per second (default: 0.5)")
    args = parser.parse_args()

    success = compile_video(args.log, args.output, args.fps)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
