import os
import struct
import time
import sys
import threading

class AsyncTrackerV4:
    def __init__(self, pid):
        self.pid = pid
        self.heap_regions = []
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
        """Thread Secundária: Varre a memória e alimenta a Thread Principal apenas com o que anda 1 tile."""
        while self.running:
            self.update_heap_map()
            snapshot = {}
            
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
                
            time.sleep(0.5) # Tempo de respiração mais rápido para respostas mais ágeis
            
            movimentados = {}
            try:
                with open(f"/proc/{self.pid}/mem", "rb") as mem:
                    for addr, (ox, oy, oz) in snapshot.items():
                        try:
                            mem.seek(addr)
                            nx, ny, nz = struct.unpack('<iii', mem.read(12))
                            dx, dy = abs(nx - ox), abs(ny - oy)
                            
                            # REGRA DE OURO V4: O personagem anda estritamente 1 tile no X ou Y por vez.
                            # Saltos maiores são artefatos da Câmera ou Minimapa e devem ser ignorados.
                            if nz == oz and (dx > 0 or dy > 0) and dx <= 1 and dy <= 1:
                                movimentados[addr] = (nx, ny, nz)
                        except Exception:
                            pass
            except Exception:
                pass
                
            agora = time.time()
            with self.lock:
                for addr, (nx, ny, nz) in movimentados.items():
                    if addr not in self.candidates:
                        self.candidates[addr] = {'x': nx, 'y': ny, 'z': nz, 'last_move': agora, 'score': 1}
                        
                # Limpa objetos que estão na lista mas pararam de existir ou não se movem há 5 segundos
                para_remover = [a for a, d in self.candidates.items() if agora - d['last_move'] > 5.0]
                for a in para_remover:
                    del self.candidates[a]
                    if self.active_target == a:
                        self.active_target = None

    def run_fast_monitor(self):
        if not self.update_heap_map():
            print("[!] Execute como root (sudo).")
            return
            
        print("="*65)
        print(" 🎯 TRACKER V4 (STRICT KINEMATICS & SCORE DECAY) ")
        print("="*65)
        print("[*] Thread Secundaria Acoplada. Ande no jogo para assumir o controle.")
        
        bg_thread = threading.Thread(target=self.background_delta_scanner)
        bg_thread.daemon = True
        bg_thread.start()
        
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                while self.running:
                    agora = time.time()
                    
                    with self.lock:
                        for addr in list(self.candidates.keys()):
                            data = self.candidates[addr]
                            try:
                                mem.seek(addr)
                                nx, ny, nz = struct.unpack('<iii', mem.read(12))
                                
                                if not (31000 < nx < 34000 and 31000 < ny < 34000 and 0 <= nz <= 15):
                                    raise ValueError("Corrompido")
                                    
                                dx, dy, dz = abs(nx - data['x']), abs(ny - data['y']), abs(nz - data['z'])
                                
                                if dx > 0 or dy > 0 or dz > 0:
                                    if dz == 0 and dx <= 1 and dy <= 1:
                                        data['score'] += 1
                                        data['last_move'] = agora
                                    elif dx > 1 or dy > 1 or dz != 0:
                                        # Sofreu Teleporte. Mantém o objeto mas zera o score de confiança
                                        data['score'] = 0
                                        data['last_move'] = agora
                                        
                                    data['x'], data['y'], data['z'] = nx, ny, nz
                                else:
                                    # AMNÉSIA SELETIVA: Se parou por 0.5s, perde a confiança.
                                    # Isso mata as câmeras e fantasmas que travavam o radar.
                                    if agora - data['last_move'] > 0.5:
                                        data['score'] = 0
                            except Exception:
                                del self.candidates[addr]
                                if self.active_target == addr:
                                    self.active_target = None
                                    
                        # --- MOTOR DE ELEIÇÃO PURIFICADO ---
                        ativos = [(a, d) for a, d in self.candidates.items() if d['score'] > 0]
                        if ativos:
                            # Elege quem tem o maior Score no momento exato
                            ativos.sort(key=lambda item: item[1]['score'], reverse=True)
                            self.active_target = ativos[0][0]

                    # Display
                    if self.active_target and self.active_target in self.candidates:
                        data = self.candidates[self.active_target]
                        estado = "[ANDANDO]" if data['score'] > 0 else "[PARADO] "
                        print(f"\r\033[K{estado} X: {data['x']} | Y: {data['y']} | Z: {data['z']}  (Score: {data['score']})", end="")
                    else:
                        print(f"\r\033[K[AGUARDANDO] Calibrando sensores... dê um passo.   ", end="")
                        
                    time.sleep(0.02) # 50Hz de taxa de atualização visual
                    
        except KeyboardInterrupt:
            self.running = False
            print("\n\n[*] Operação finalizada.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: sudo python3 bot_tracker_v4.py [PID]")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    tracker = AsyncTrackerV4(pid)
    tracker.run_fast_monitor()