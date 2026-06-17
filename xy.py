import os
import struct
import time
import sys

class XYScanner:
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

    def capture_stance(self):
        print("[*] FASE 1: Fotografando a malha espacial atual...")
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                for start, end in self.heap_regions:
                    mem.seek(start)
                    try: dump = mem.read(end - start)
                    except OSError: continue
                    
                    for offset in range(0, len(dump) - 12, 4):
                        x, y, z = struct.unpack_from('<iii', dump, offset)
                        
                        if 31000 < x < 34000 and 31000 < y < 34000 and 0 <= z <= 15:
                            self.snapshot[start + offset] = (x, y, z)
                            
            print(f"[+] Snapshot capturado: {len(self.snapshot)} blocos com coordenadas válidas.")
        except Exception as e:
            print(f"[!] Erro no I/O: {e}")

    def analyze_step(self):
        print("\n[*] FASE 2: Filtrando blocos pela física estrita de 1 tile...")
        valid_structures = []
        
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                for addr, (ox, oy, oz) in self.snapshot.items():
                    try:
                        mem.seek(addr)
                        nx, ny, nz = struct.unpack('<iii', mem.read(12))
                        
                        dx = abs(nx - ox)
                        dy = abs(ny - oy)
                        dz = abs(nz - oz)
                        
                        # A Regra Absoluta do Passo Simples (Cardeais)
                        # O Z não muda. Eixo X muda 1 e Y muda 0, OU Eixo Y muda 1 e X muda 0.
                        if dz == 0 and ((dx == 1 and dy == 0) or (dx == 0 and dy == 1)):
                            eixo_movido = "Eixo X (Leste/Oeste)" if dx == 1 else "Eixo Y (Norte/Sul)"
                            valid_structures.append({
                                'addr': addr,
                                'old': (ox, oy, oz),
                                'new': (nx, ny, nz),
                                'eixo': eixo_movido
                            })
                    except Exception:
                        pass
        except Exception:
            pass

        return valid_structures

    def run(self):
        print("="*60)
        print(" 🧭 ISOLADOR DO PLANO CARTESIANO (X/Y X-RAY) ")
        print("="*60)
        
        print("-> Fique parado em uma área plana (sem escadas).")
        input("Pressione [ENTER] quando estiver pronto...")
        
        self.capture_stance()
        
        print("\n-> VÁ PARA O JOGO E DÊ UM (1) ÚNICO PASSO RETO (Cima, Baixo, Esquerda ou Direita).")
        print("-> Não ande na diagonal.")
        input("Pressione [ENTER] APÓS o personagem terminar o passo...")
        
        resultados = self.analyze_step()
        
        print("\n" + "="*60)
        print(" RESULTADOS DA AFERIÇÃO ESTÁTICA")
        print("="*60)
        
        if not resultados:
            print("[-] Nenhuma estrutura sobreviveu à física estrita de 1 tile.")
            print("[-] Você andou mais de 1 tile, ou andou na diagonal, ou a RAM limpou os objetos.")
        else:
            print(f"[+] {len(resultados)} estruturas isoladas com física bidimensional perfeita:\n")
            for r in resultados:
                print(f"Endereço: {hex(r['addr'])} -> Movimento detectado no {r['eixo']}")
                print(f"   Antes  -> X: {r['old'][0]} | Y: {r['old'][1]} | Z: {r['old'][2]}")
                print(f"   Depois -> X: {r['new'][0]} | Y: {r['new'][1]} | Z: {r['new'][2]}")
                print("-" * 50)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: sudo python3 xy.py [PID]")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    scanner = XYScanner(pid)
    
    if scanner.map_heap():
        scanner.run()