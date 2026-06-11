import os
import struct
import time
import sys
import threading

class AsyncTrackerV2:
    def __init__(self, pid):
        self.pid = pid
        self.heap_regions = []
        # Apenas objetos que provaram movimento entram aqui
        self.candidates = {} 
        self.active_target = None
        self.lock = threading.Lock()
        self.running = True
        
    def update_heap_map(self):
        regions = []
        try:
            with open(f"/proc/{self.pid}/maps", "r") as maps:
                for line in maps:
                    parts = line.split()
                    if len(parts) < 5: continue
                    if "rw-p" in parts[1] and "bin/client" not in line:
                        start, end = [int(x, 16) for x in parts[0].split('-')]
                        regions.append((start, end))
            self.heap_regions = regions
            return True
        except Exception:
            return False

    def background_delta_scanner(self):
        """THREAD 2: Compara snapshots e alimenta a Main Thread APENAS com o que se move."""
        while self.running:
            self.update_heap_map()
            snapshot = {}
            
            # 1. Tira a primeira foto da memória (Lote massivo)
            try:
                with open(f"/proc/{self.pid}/mem", "rb") as mem:
                    for start, end in self.heap_regions:
                        mem.seek(start)
                        try: dump = mem.read(end - start)
                        except OSError: continue
                        
                        for offset in range(0, len(dump) - 12, 4):
                            x, y, z = struct.unpack_from('<iii', dump, offset)
                            if 31000 < x < 34000 and 31000 < y < 34000 and 0 <= z <= 15:
                                snapshot[start + offset] = (x, y, z)
            except Exception:
                pass
                
            time.sleep(1.0) # Aguarda a física do jogo acontecer
            
            # 2. Tira a segunda foto e processa o Delta (Isola apenas quem andou)
            movimentados = {}
            try:
                with open(f"/proc/{self.pid}/mem", "rb") as mem:
                    for addr, (ox, oy, oz) in snapshot.items():
                        try:
                            mem.seek(addr)
                            nx, ny, nz = struct.unpack('<iii', mem.read(12))
                            dx, dy = abs(nx - ox), abs(ny - oy)
                            
                            # Se deu um passo válido
                            if nz == oz and (dx > 0 or dy > 0) and dx <= 2 and dy <= 2:
                                movimentados[addr] = (nx, ny, nz)
                        except Exception:
                            pass
            except Exception:
                pass
                
            # 3. Entrega os objetos limpos para a lista oficial
            agora = time.time()
            with self.lock:
                for addr, (nx, ny, nz) in movimentados.items():
                    if addr not in self.candidates:
                        self.candidates[addr] = {'x': nx, 'y': ny, 'z': nz, 'last_move': agora, 'score': 1}
                        
                # Auto-Limpeza: Remove candidatos que estão parados há mais de 10 segundos
                para_remover = [a for a, d in self.candidates.items() if agora - d['last_move'] > 10.0]
                for a in para_remover:
                    if a != self.active_target: # Nunca removemos o campeão atual
                        del self.candidates[a]

    def run_fast_monitor(self):
        """THREAD 1: Monitora de 5 a 20 objetos a 50Hz. Tempo de resposta quase zero."""
        if not self.update_heap_map():
            print("[!] Execute como root (sudo).")
            return
            
        print("="*65)
        print(" 🚀 TRACKER ASSÍNCRONO V2 (DELTA PRE-FILTERING) ")
        print("="*65)
        print("[*] Levantando Malha de Fundo... (Aguarde 2s e comece a andar)")
        
        bg_thread = threading.Thread(target=self.background_delta_scanner)
        bg_thread.daemon = True
        bg_thread.start()
        
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                while self.running:
                    agora = time.time()
                    
                    with self.lock:
                        # Varre apenas os alvos peneirados pela Thread de Fundo
                        for addr in list(self.candidates.keys()):
                            data = self.candidates[addr]
                            try:
                                mem.seek(addr)
                                nx, ny, nz = struct.unpack('<iii', mem.read(12))
                                
                                # Sanidade e Destruição
                                if not (31000 < nx < 34000 and 31000 < ny < 34000 and 0 <= nz <= 15):
                                    raise ValueError("Corrompido")
                                    
                                dx, dy, dz = abs(nx - data['x']), abs(ny - data['y']), abs(nz - data['z'])
                                
                                if dx > 0 or dy > 0 or dz > 0:
                                    if dz == 0 and dx <= 2 and dy <= 2:
                                        data['score'] += 1
                                        data['last_move'] = agora
                                    elif dx > 2 or dy > 2 or dz != 0:
                                        # Teleporte: Atualiza as coords, mantemos o target vivo
                                        data['last_move'] = agora
                                        
                                    data['x'], data['y'], data['z'] = nx, ny, nz
                            except Exception:
                                del self.candidates[addr]
                                if self.active_target == addr:
                                    self.active_target = None
                                    
                        # Eleição do Alvo (Líder)
                        ativos = [(a, d) for a, d in self.candidates.items() if d['score'] > 0]
                        if ativos:
                            # Ordenamos por Pontuação. Empates são decididos a favor do Alvo já ativo (Âncora de Liderança)
                            ativos.sort(key=lambda item: (item[1]['score'] + (1 if item[0] == self.active_target else 0)), reverse=True)
                            self.active_target = ativos[0][0]

                    # Tela Pura
                    if self.active_target:
                        data = self.candidates[self.active_target]
                        estado = "[ANDANDO]" if agora - data['last_move'] <= 2.0 else "[PARADO] "
                        print(f"\r\033[K{estado} X: {data['x']} | Y: {data['y']} | Z: {data['z']}  (Hit: {data['score']})", end="")
                    else:
                        print(f"\r\033[K[AGUARDANDO] Reconhecimento Delta... dê alguns passos.   ", end="")
                        
                    # Taxa de Atualização: 50Hz (20ms) - Ultra Fluído
                    time.sleep(0.02)
                    
        except KeyboardInterrupt:
            self.running = False
            print("\n\n[*] Operação finalizada.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: sudo python3 bot_tracker_v2.py [PID]")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    tracker = AsyncTrackerV2(pid)
    tracker.run_fast_monitor()