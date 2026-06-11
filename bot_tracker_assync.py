import os
import struct
import time
import sys
import threading

class AsyncTracker:
    def __init__(self, pid):
        self.pid = pid
        self.heap_regions = []
        # Dicionário de candidatos: { endereco: {'x': x, 'y': y, 'z': z, 'last_move': 0.0, 'score': 0} }
        self.candidates = {} 
        self.lock = threading.Lock()
        self.running = True
        
    def update_heap_map(self):
        """Atualiza o mapa de memória disponível."""
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

    def background_scanner(self):
        """THREAD 2: Varre 1GB de RAM a cada 2 segundos em busca de novos objetos."""
        while self.running:
            self.update_heap_map()
            novos_candidatos = {}
            
            try:
                with open(f"/proc/{self.pid}/mem", "rb") as mem:
                    for start, end in self.heap_regions:
                        mem.seek(start)
                        try: dump = mem.read(end - start)
                        except OSError: continue
                        
                        # Extração em lote de vetores espaciais
                        for offset in range(0, len(dump) - 12, 4):
                            x, y, z = struct.unpack_from('<iii', dump, offset)
                            
                            # Filtro Geográfico Brutal do Tibia Global
                            if 31000 < x < 34000 and 31000 < y < 34000 and 0 <= z <= 15:
                                addr = start + offset
                                novos_candidatos[addr] = (x, y, z)
            except Exception:
                pass
                
            # Adiciona os novos endereços à lista monitorada sem quebrar a leitura da Thread principal
            with self.lock:
                for addr, (x, y, z) in novos_candidatos.items():
                    if addr not in self.candidates:
                        self.candidates[addr] = {'x': x, 'y': y, 'z': z, 'last_move': 0.0, 'score': 0}
                        
            time.sleep(2.0) # Espera 2 segundos para não asfixiar a CPU

    def run_fast_monitor(self):
        """THREAD 1: Monitora movimento a 100Hz e exibe a coordenada ativa."""
        if not self.update_heap_map():
            print("[!] Falha ao mapear memória. Rode como root.")
            return
            
        print("="*60)
        print(" 🛰️ TRACKER ASSÍNCRONO (MULTI-THREADED STALKER) ")
        print("="*60)
        print("[*] Iniciando Scanner de Fundo...")
        
        # Inicia a Thread Secundária
        bg_thread = threading.Thread(target=self.background_scanner)
        bg_thread.daemon = True
        bg_thread.start()
        
        print("\n\033[K[+] Radar Online! Ande no jogo para assumir o controle.")
        
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                while self.running:
                    agora = time.time()
                    melhor_candidato = None
                    
                    with self.lock:
                        # Iteramos sobre uma cópia estática das chaves para permitir exclusão
                        for addr in list(self.candidates.keys()):
                            data = self.candidates[addr]
                            try:
                                mem.seek(addr)
                                nx, ny, nz = struct.unpack('<iii', mem.read(12))
                                
                                # Auto-Limpeza: Se o objeto foi sobrescrito por lixo de RAM, apague-o
                                if not (31000 < nx < 34000 and 31000 < ny < 34000 and 0 <= nz <= 15):
                                    del self.candidates[addr]
                                    continue
                                    
                                dx, dy, dz = abs(nx - data['x']), abs(ny - data['y']), abs(nz - data['z'])
                                
                                if dx > 0 or dy > 0 or dz > 0:
                                    if dx <= 2 and dy <= 2 and dz == 0:
                                        # FÍSICA VÁLIDA: O objeto deu um passo. Registramos o momento exato.
                                        data['score'] += 1
                                        data['last_move'] = agora
                                    elif dx > 2 or dy > 2 or dz != 0:
                                        # TELEPORTE/ANDAR: Movimento drástico. Atualizamos, mas não pontuamos.
                                        data['last_move'] = agora
                                        
                                    # Sincroniza a memória com o estado atual
                                    data['x'], data['y'], data['z'] = nx, ny, nz
                                    
                            except Exception:
                                # Bloco destruído pelo sistema operacional
                                del self.candidates[addr]
                                
                        # ELEIÇÃO: O Verdadeiro LocalPlayer é o objeto que se moveu mais recentemente
                        ativos = [v for v in self.candidates.values() if v['score'] > 0]
                        if ativos:
                            # Ordenamos primeiro por Recência de Movimento, depois por Consistência (Score)
                            ativos.sort(key=lambda v: (v['last_move'], v['score']), reverse=True)
                            melhor_candidato = ativos[0]

                    # Módulo de Display Fluido (Substitui apenas o texto atual)
                    if melhor_candidato:
                        tempo_ocioso = agora - melhor_candidato['last_move']
                        if tempo_ocioso > 3.0:
                            print(f"\r\033[K[PARADO] X: {melhor_candidato['x']} | Y: {melhor_candidato['y']} | Z: {melhor_candidato['z']}      ", end="")
                        else:
                            print(f"\r\033[K[ANDANDO] X: {melhor_candidato['x']} | Y: {melhor_candidato['y']} | Z: {melhor_candidato['z']}      ", end="")
                    else:
                        print(f"\r\033[K[AGUARDANDO] Dê um passo no jogo para conectar...      ", end="")
                        
                    time.sleep(0.05)
                    
        except KeyboardInterrupt:
            self.running = False
            print("\n\n[*] Radar Desligado e Threads Encerradas.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: sudo python3 bot_tracker_async.py [PID]")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    tracker = AsyncTracker(pid)
    tracker.run_fast_monitor()