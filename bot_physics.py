import os
import struct
import time
import sys

class PhysicsScanner:
    def __init__(self, pid):
        self.pid = pid
        self.heap_regions = []
        self.candidates = []
        
    def map_heap(self):
        try:
            with open(f"/proc/{self.pid}/maps", "r") as maps:
                for line in maps:
                    parts = line.split()
                    if len(parts) < 5: continue
                    if "rw-p" in parts[1] and "bin/client" not in line:
                        start, end = [int(x, 16) for x in parts[0].split('-')]
                        self.heap_regions.append((start, end))
            return True
        except PermissionError:
            print("[!] Execute como root (sudo).")
            return False

    def scan_triplet(self, x, y, z):
        print(f"[*] Escaneando Heap pelas coordenadas absolutas: X={x}, Y={y}, Z={z}...")
        # Empacota os 3 inteiros sequenciais na ordem X, Y, Z (12 bytes no total)
        target_bytes = struct.pack('<iii', x, y, z)
        
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                for start, end in self.heap_regions:
                    mem.seek(start)
                    try: dump = mem.read(end - start)
                    except OSError: continue
                    
                    offset = 0
                    while True:
                        offset = dump.find(target_bytes, offset)
                        if offset == -1: break
                        
                        self.candidates.append(start + offset)
                        offset += 12
            print(f"[+] {len(self.candidates)} vetores encontrados.")
            return len(self.candidates) > 0
        except Exception as e:
            print(f"[!] Erro de leitura: {e}")
            return False

    def poll_and_filter(self):
        if not self.candidates:
            return
            
        print("\n" + "="*60)
        print(" MOTOR DE RASTREAMENTO FÍSICO ATIVO ")
        print(" VÁ PARA O JOGO E ANDE ALGUMAS VEZES EM QUALQUER DIREÇÃO")
        print("="*60)
        
        # O bloco de vizinhança assumido baseado na arquitetura da UI
        # Vamos olhar 32 bytes para a esquerda e 64 bytes para a direita das coordenadas
        
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                while True:
                    survivors = []
                    
                    # Limpa a tela para atualizar a matriz
                    print("\033[H\033[J")
                    print(f"Rastreando {len(self.candidates)} estruturas em tempo real...\n")
                    
                    for addr in self.candidates:
                        try:
                            # Lê o vetor X, Y, Z
                            mem.seek(addr)
                            x, y, z = struct.unpack('<iii', mem.read(12))
                            
                            # Lê os possíveis atributos vitais (+ 128 bytes para cima do X)
                            mem.seek(addr + 128)
                            vitals = struct.unpack('<iiii', mem.read(16))
                            
                            short_addr = hex(addr)[-5:]
                            print(f"[{short_addr}] Coords: X:{x:<5} Y:{y:<5} Z:{z:<2} | Vizinhança (+128b): {vitals}")
                            
                            survivors.append(addr)
                        except Exception:
                            pass
                            
                    self.candidates = survivors
                    time.sleep(0.5)
        except KeyboardInterrupt:
            print("\n[*] Monitoramento encerrado.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: sudo python3 bot_physics.py [PID]")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    scanner = PhysicsScanner(pid)
    
    if not scanner.map_heap():
        sys.exit(1)
        
    print("Para iniciar, precisamos da sua coordenada EXATA atual.")
    print("Abra o mapa do jogo (ou olhe no terminal anterior de logs) e digite os valores.")
    try:
        x = int(input("Coordenada X (Ex: 31951): "))
        y = int(input("Coordenada Y (Ex: 31906): "))
        z = int(input("Coordenada Z (Ex: 7): "))
    except ValueError:
        sys.exit(1)
        
    if scanner.scan_triplet(x, y, z):
        scanner.poll_and_filter()
    else:
        print("[-] Nenhuma estrutura contendo essa coordenada exata foi encontrada. Verifique os números.")