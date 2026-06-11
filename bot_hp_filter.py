import os
import struct
import sys

class HPFilter:
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

    def first_scan(self, hp_atual):
        print(f"[*] Varrendo a Heap buscando a Vida Atual: {hp_atual}...")
        hp_bytes = struct.pack('<i', hp_atual)
        
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                for start, end in self.heap_regions:
                    mem.seek(start)
                    try: dump = mem.read(end - start)
                    except OSError: continue
                    
                    offset = 0
                    while True:
                        offset = dump.find(hp_bytes, offset)
                        if offset == -1: break
                        
                        self.candidates.add(start + offset)
                        offset += 4 
        except Exception as e:
            print(f"[!] Erro de leitura: {e}")
            
        print(f"[+] {len(self.candidates)} blocos encontrados na memória.")

    def next_scan(self, novo_hp):
        print(f"[*] Filtrando candidatos para a nova Vida: {novo_hp}...")
        hp_bytes = struct.pack('<i', novo_hp)
        survivors = set()
        
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                for addr in self.candidates:
                    try:
                        mem.seek(addr)
                        if mem.read(4) == hp_bytes:
                            survivors.add(addr)
                    except Exception:
                        pass # O bloco morreu (era buffer temporário da barra vermelha)
        except Exception as e:
            print(f"[!] Erro de leitura: {e}")
            
        self.candidates = survivors
        print(f"[+] Restam {len(self.candidates)} blocos vitais persistentes.")

    def show_results(self):
        print("\n" + "="*50)
        print(" ESTRUTURAS VITAIS SOBREVIVENTES")
        print("="*50)
        for addr in self.candidates:
            print(f" -> {hex(addr)}")
        print("="*50 + "\n")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: sudo python3 bot_hp_filter.py [PID]")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    scanner = HPFilter(pid)
    
    if not scanner.map_heap():
        sys.exit(1)
        
    print("="*55)
    print(" AFINILAMENTO DE VIDA (STATEFUL SCANNER)")
    print("="*55)
    print("REGRA: Sua vida NÃO PODE estar cheia para evitar colisão com Vida Máxima.\n")
    
    try:
        hp1 = int(input("1. Digite seu HP Atual (ex: 210): "))
        scanner.first_scan(hp1)
        
        while True:
            if len(scanner.candidates) == 0:
                print("[-] Todos os candidatos morreram. A engine recria a vida do zero a cada hit.")
                break
                
            if len(scanner.candidates) <= 10: # Limite mais flexível para vermos os resultados
                print("\n[!] Ruído eliminado! Blocos isolados.")
                scanner.show_results()
                break
                
            print("\n-> Vá para o jogo, TOME DANO e aguarde 2 segundos.")
            hpn = int(input("2. Digite o NOVO HP Atual: "))
            scanner.next_scan(hpn)
            
    except ValueError:
        print("\n[!] Entrada inválida. Encerrando.")
    except KeyboardInterrupt:
        print("\n[!] Cancelado pelo usuário.")