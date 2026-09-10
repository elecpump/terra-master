"""TerraBridge protocol 1 client. Python standard library only."""
import argparse
import json
import socket
import sys
import time


def request(command="observe", port=17655):
    with socket.create_connection(("127.0.0.1", port), timeout=3) as sock:
        sock.sendall((command + "\n").encode("ascii"))
        with sock.makefile("rb") as reader:
            data = reader.readline(65537)
    if not data.endswith(b"\n") or len(data) > 65536:
        raise ValueError("Incomplete or oversized bridge response")
    result = json.loads(data)
    if result.get("protocol") != 1 or "error" in result:
        raise ValueError(f"Unexpected bridge response: {result}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["ping", "observe", "watch", "act", "stop"], default="observe", nargs="?")
    parser.add_argument("action", choices=["left", "right", "jump", "left_jump", "right_jump"], nargs="?")
    parser.add_argument("--ms", type=int, default=250)
    parser.add_argument("--port", type=int, default=17655)
    args = parser.parse_args()
    if args.command == "act" and (args.action is None or not 1 <= args.ms <= 1000):
        parser.error("act requires an action and --ms between 1 and 1000")
    try:
        while True:
            command = f"act {args.action} {args.ms}" if args.command == "act" else args.command
            result = request("observe" if command == "watch" else command, args.port)
            if "sampledAtUnixMs" in result:
                result["sampleAgeMs"] = round(time.time() * 1000 - result["sampledAtUnixMs"])
            print(json.dumps(result, ensure_ascii=False), flush=True)
            if args.command != "watch":
                return 0
            time.sleep(0.5)
    except (OSError, ValueError) as exc:
        print(f"Bridge unavailable: {exc}. Start tModLoader with TerraBridge enabled.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
