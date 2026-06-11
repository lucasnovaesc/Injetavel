import os
import struct
import sys

class CoordFilter:
    def __init__(self, pid):
        self.pid = pid
        self.heap_regions = []
        self.candidates = set()
        
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

    def first_scan(self, x, y, z):
        print(f"[*] Varrendo a Heap pelas coordenadas: X={x}, Y={y}, Z={z}...")
        coord_bytes = struct.pack('<iii', x, y, z)
        
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                for start, end in self.heap_regions:
                    mem.seek(start)
                    try: dump = mem.read(end - start)
                    except OSError: continue
                    
                    offset = 0
                    while True:
                        offset = dump.find(coord_bytes, offset)
                        if offset == -1: break
                        
                        self.candidates.add(start + offset)
                        offset += 12 
        except Exception as e:
            print(f"[!] Erro de leitura: {e}")
            
        print(f"[+] {len(self.candidates)} vetores espaciais encontrados na memória.")

    def next_scan(self, x, y, z):
        print(f"[*] Filtrando candidatos para a nova posição: X={x}, Y={y}, Z={z}...")
        coord_bytes = struct.pack('<iii', x, y, z)
        survivors = set()
        
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                for addr in self.candidates:
                    try:
                        mem.seek(addr)
                        if mem.read(12) == coord_bytes:
                            survivors.add(addr)
                    except Exception:
                        pass # O bloco morreu (era buffer temporário de rede ou renderização)
        except Exception as e:
            print(f"[!] Erro de leitura: {e}")
            
        self.candidates = survivors
        print(f"[+] Restam {len(self.candidates)} vetores persistentes.")

    def show_results(self):
        print("\n" + "="*50)
        print(" VETOR FÍSICO RAIZ ENCONTRADO (LOCALPLAYER)")
        print("="*50)
        for addr in self.candidates:
            print(f" -> {hex(addr)}")
        print("="*50 + "\n")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: sudo python3 bot_coord_filter.py [PID]")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    scanner = CoordFilter(pid)
    
    if not scanner.map_heap():
        sys.exit(1)
        
    print("="*55)
    print(" AFINILAMENTO DE COORDENADAS (STATEFUL SCANNER)")
    print("="*55)
    
    try:
        x1 = int(input("1. Digite o X Atual: "))
        y1 = int(input("1. Digite o Y Atual: "))
        z1 = int(input("1. Digite o Z Atual: "))
        scanner.first_scan(x1, y1, z1)
        
        while True:
            if len(scanner.candidates) == 0:
                print("[-] Todos os candidatos morreram. A engine realoca coordenadas dinamicamente.")
                break
                
            if len(scanner.candidates) <= 8:
                print("\n[!] Ruído eliminado! Objeto físico isolado.")
                scanner.show_results()
                break
                
            print("\n-> Vá para o jogo, DÊ ALGUNS PASSOS E PARE.")
            xn = int(input("2. Digite o NOVO X: "))
            yn = int(input("2. Digite o NOVO Y: "))
            zn = int(input("2. Digite o NOVO Z (geralmente o mesmo): "))
            scanner.next_scan(xn, yn, zn)
            
    except ValueError:
        print("\n[!] Entrada inválida. Encerrando.")
    except KeyboardInterrupt:
        print("\n[!] Cancelado pelo usuário.")