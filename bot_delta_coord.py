import os
import struct
import sys

class DeltaCoordTracker:
    def __init__(self, pid):
        self.pid = pid
        self.heap_regions = []
        self.candidates = {} # Formato: {endereco: (X, Y, Z)}
        
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

    def initial_scan(self):
        print("[*] Mapeando a matriz espacial do jogo. Isso pode levar de 5 a 15 segundos...")
        print("[*] Aguarde a conclusão antes de se mover no jogo.")
        
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                for start, end in self.heap_regions:
                    mem.seek(start)
                    try: dump = mem.read(end - start)
                    except OSError: continue
                    
                    # Leitura em lote otimizada
                    for offset in range(0, len(dump) - 12, 4):
                        x, y, z = struct.unpack_from('<iii', dump, offset)
                        
                        # Filtro Geográfico Brutal: Apenas entidades contidas nos limites do mapa do Tibia
                        if 31000 < x < 34000 and 31000 < y < 34000 and 0 <= z <= 15:
                            addr = start + offset
                            self.candidates[addr] = (x, y, z)
                            
            print(f"[+] Snapshot concluído. {len(self.candidates)} entidades e blocos espaciais capturados.")
        except Exception as e:
            print(f"[!] Erro crítico na leitura: {e}")

    def delta_filter(self):
        print("\n[*] Filtrando pelo Delta de Movimento...")
        survivors = {}
        
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                for addr, (old_x, old_y, old_z) in self.candidates.items():
                    try:
                        mem.seek(addr)
                        new_x, new_y, new_z = struct.unpack('<iii', mem.read(12))
                        
                        # Calculamos a diferença de movimento (Delta)
                        delta_x = abs(new_x - old_x)
                        delta_y = abs(new_y - old_y)
                        delta_z = abs(new_z - old_z)
                        
                        # O jogador só pode dar 1 passo de cada vez (incluindo diagonais)
                        # Portanto, o Z não muda, e a soma dos passos X e Y deve ser 1 ou 2 (diagonal)
                        movimento_valido = (delta_z == 0) and (1 <= (delta_x + delta_y) <= 2) and (delta_x <= 1 and delta_y <= 1)
                        
                        if movimento_valido:
                            survivors[addr] = (new_x, new_y, new_z)
                    except Exception:
                        pass # Bloco descartado pelo sistema
        except Exception as e:
            print(f"[!] Erro de leitura: {e}")
            
        self.candidates = survivors
        print(f"[+] Restam {len(self.candidates)} entidades reativas.")

    def show_results(self):
        print("\n" + "="*50)
        print(" VETORES ESPACIAIS DO JOGADOR ISOLADOS ")
        print("="*50)
        for addr, (x, y, z) in self.candidates.items():
            print(f" -> {hex(addr)} | X: {x}, Y: {y}, Z: {z}")
        print("="*50 + "\n")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: sudo python3 bot_delta_coord.py [PID]")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    tracker = DeltaCoordTracker(pid)
    
    if not tracker.map_heap():
        sys.exit(1)
        
    print("="*60)
    print(" SCANNER DE MOVIMENTO RELATIVO (DELTA TRACKER)")
    print("="*60)
    
    tracker.initial_scan()
    
    while True:
        if len(tracker.candidates) == 0:
            print("[-] Todas as entidades foram perdidas. A engine recriou a matriz.")
            break
            
        if len(tracker.candidates) <= 8:
            print("\n[!] Ruído espacial eliminado. Estruturas raiz isoladas.")
            tracker.show_results()
            break
            
        print("\n-> VÁ PARA O JOGO, DÊ UM ÚNICO PASSO E PARE (Aguarde 1 segundo).")
        input("Pressione [ENTER] no terminal APÓS dar o passo...")
        tracker.delta_filter()