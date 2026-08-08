"""
main.py
=======
This is the "on" button for Lock In.

Run it like this:
    python main.py

This file stays small on purpose. It has two jobs: check that the needed
pieces are installed (and explain nicely if they're not), then hand things
off to the app's screen. All the real code lives in the `lock_in`
folder, kept together so the app-building tool can find it easily.
"""

from __future__ import annotations

import sys


def check_dependencies() -> list[str]:
    """
    Look for missing extra pieces and make a list of friendly warnings.

    Only `customtkinter` is a must-have — without it the app can't even
    draw its window. Everything else is a nice-to-have: if it's missing,
    one feature turns off, but the app still runs.
    """
    warnings: list[str] = []

    try:
        import customtkinter  # noqa: F401
    except ImportError:
        print("FATAL: customtkinter is required.\n  pip install customtkinter",
              file=sys.stderr)
        sys.exit(1)

    if sys.platform == "win32":
        try:
            import win32gui  # noqa: F401
            import psutil    # noqa: F401
        except ImportError:
            warnings.append(
                "pywin32 / psutil not found — app detection is disabled.\n"
                "  pip install pywin32 psutil"
            )
        try:
            import winotify  # noqa: F401
        except ImportError:
            warnings.append(
                "winotify not found — using in-app banners instead of toasts.\n"
                "  pip install winotify"
            )
    else:
        warnings.append(
            f"Running on {sys.platform}: window detection is limited and window "
            "minimising is unavailable. The timer itself works normally."
        )

    return warnings


def main() -> None:
    for warning in check_dependencies():
        print(f"[warn] {warning}")

    from lock_in.ui import run
    run()


if __name__ == "__main__":
    main()