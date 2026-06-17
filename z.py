import os
import struct
import time
import sys

class ZScanner:
    def __init__(self, pid):
        self.pid = pid
        self.heap_regions = []
        self.snapshot = {}

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

    def capture_base_floor(self):
        print("[*] FASE 1: Tirando foto do andar atual...")
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                for start, end in self.heap_regions:
                    mem.seek(start)
                    try: dump = mem.read(end - start)
                    except OSError: continue
                    
                    for offset in range(0, len(dump) - 12, 4):
                        x, y, z = struct.unpack_from('<iii', dump, offset)
                        
                        # Filtro Geográfico do Tibia Lógico (Z deve ser de 0 a 15)
                        if 31000 < x < 34000 and 31000 < y < 34000 and 0 <= z <= 15:
                            self.snapshot[start + offset] = (x, y, z)
                            
            print(f"[+] Snapshot capturado: {len(self.snapshot)} blocos com Z válido.")
        except Exception as e:
            print(f"[!] Erro no I/O: {e}")

    def analyze_z_transition(self):
        print("\n[*] FASE 2: Filtrando pela física de transição de andar...")
        valid_z_structures = []
        
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                for addr, (ox, oy, oz) in self.snapshot.items():
                    try:
                        mem.seek(addr)
                        nx, ny, nz = struct.unpack('<iii', mem.read(12))
                        
                        dx = abs(nx - ox)
                        dy = abs(ny - oy)
                        dz = nz - oz # Pode ser negativo ou positivo
                        
                        # A regra de ouro da transição de andar:
                        # O Z deve mudar EXATAMENTE 1 ou -1.
                        # O X e Y devem mudar no máximo 2 blocos (caso de escadas em diagonal/rampas).
                        if abs(dz) == 1 and dx <= 2 and dy <= 2:
                            valid_z_structures.append({
                                'addr': addr,
                                'old': (ox, oy, oz),
                                'new': (nx, ny, nz),
                                'delta_z': dz
                            })
                    except Exception:
                        pass
        except Exception:
            pass

        return valid_z_structures

    def run(self):
        print("="*60)
        print(" 📐 ISOLADOR DO EIXO Z (LOGICAL FLOOR SCANNER) ")
        print("="*60)
        
        print("-> Fique parado EXATAMENTE ao lado de uma escada ou buraco.")
        input("Pressione [ENTER] quando estiver pronto...")
        
        self.capture_base_floor()
        
        print("\n-> VÁ PARA O JOGO E MUDE DE ANDAR (Suba/Desça a escada).")
        input("Pressione [ENTER] APÓS terminar a transição de andar...")
        
        resultados = self.analyze_z_transition()
        
        print("\n" + "="*60)
        print(" RESULTADOS DA AFERIÇÃO DO EIXO Z")
        print("="*60)
        
        if not resultados:
            print("[-] Nenhuma estrutura obedeceu à física do servidor.")
            print("[-] Isso significa que o objeto da memória é recriado ao mudar de andar.")
        else:
            print(f"[+] {len(resultados)} estruturas isoladas com física de Z perfeita:\n")
            for r in resultados:
                print(f"Endereço: {hex(r['addr'])}")
                print(f"   Antes  -> X: {r['old'][0]} | Y: {r['old'][1]} | Z: {r['old'][2]}")
                print(f"   Depois -> X: {r['new'][0]} | Y: {r['new'][1]} | Z: {r['new'][2]}")
                print("-" * 40)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: sudo python3 z.py [PID]")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    scanner = ZScanner(pid)
    
    if scanner.map_heap():
        scanner.run()