"""Quick test: does cloudflared steal port 8000?"""
import subprocess, time, socket

proc = subprocess.Popen(
    [r"C:\Users\USER\AppData\Roaming\Python\Python310\site-packages\pycloudflared\cloudflared-windows-amd64.exe",
     "tunnel", "--url", "http://127.0.0.1:8000"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
print(f"cloudflared PID: {proc.pid}")
time.sleep(6)

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.bind(("0.0.0.0", 8000))
    print("Bind OK - port 8000 is FREE")
    s.close()
except Exception as e:
    print(f"Bind FAILED - cloudflared took port 8000: {e}")

proc.terminate()
