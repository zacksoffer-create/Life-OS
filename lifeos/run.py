"""Start LIFE OS: python run.py  (then open http://127.0.0.1:8765)

  --phone   also let phones on the same Wi-Fi connect, and open the "play on your phone" page with a QR code
"""
import argparse
import os
import sys
import threading
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "backend"))


def main():
    ap = argparse.ArgumentParser(description="LIFE OS - Living World Laboratory")
    ap.add_argument("--host", default=None)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--phone", "--lan", dest="phone", action="store_true",
                    help="let phones on the same Wi-Fi connect (listens on your local network)")
    ap.add_argument("--no-browser", action="store_true", help="don't open a browser tab")
    ap.add_argument("--fresh", action="store_true", help="ignore the autosave and start the demo world over")
    args = ap.parse_args()
    host = args.host or ("0.0.0.0" if args.phone else "127.0.0.1")
    os.environ["LIFEOS_PORT"] = str(args.port)
    os.environ["LIFEOS_LAN"] = "1" if host == "0.0.0.0" else "0"
    import uvicorn
    from lifeos import api
    from lifeos.phone_api import lan_ips
    from lifeos.storage import Store
    print("Loading the world...")
    api.lab = api.Lab(Store(), fresh=args.fresh)
    local = f"http://127.0.0.1:{args.port}"
    print(f"LIFE OS is running at {local}  (Ctrl+C to stop)")
    page = local
    if host == "0.0.0.0":
        ips = lan_ips()
        print("")
        print("  Play on your phone (same Wi-Fi as this computer):")
        for ip in ips or ["<this computer's IP address>"]:
            print(f"      http://{ip}:{args.port}/#/m")
        print("  If Windows asks about the firewall, allow access on private networks.")
        print("")
        page = f"{local}/#/connect"
    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(page)).start()
    uvicorn.run(api.app, host=host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
