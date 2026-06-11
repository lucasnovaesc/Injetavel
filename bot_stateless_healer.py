import os
import struct
import time
import sys
import subprocess

class StatelessHealer:
    def __init__(self, pid, max_hp, max_mana):
        self.pid = pid
        self.max_hp = max_hp
        self.max_mana = max_mana
        self.heap_regions = []
        
        # --- CONFIGURAÇÕES DE AÇÃO ---
        self.hp_cura = 200        
        self.tecla_cura = "F1"    
        self.mana_potion = 50     
        self.tecla_potion = "F2"  
        self.cooldown = 1.0       
        
        self.ultimo_heal = 0
        self.ultima_potion = 0

    def map_heap(self):
        try:
            with open(f"/proc/{self.pid}/maps", "r") as maps:
                for line in maps:
                    parts = line.split()
                    if len(parts) < 5: continue
                    # Focamos em toda memória rw-p que não seja o binário
                    if "rw-p" in parts[1] and "bin/client" not in line:
                        start, end = [int(x, 16) for x in parts[0].split('-')]
                        self.heap_regions.append((start, end))
            return True
        except PermissionError:
            print("[!] Erro: Execute como root.")
            return False

    def scan_and_read(self):
        """Varre a memória atrás da Vida/Mana Máxima e retorna os valores atuais."""
        # Empacota o MaxHP e MaxMana para a busca binária rápida
        max_hp_bytes = struct.pack('<i', self.max_hp)
        max_mana_bytes = struct.pack('<i', self.max_mana)
        
        try:
            with open(f"/proc/{self.pid}/mem", "rb") as mem:
                for start, end in self.heap_regions:
                    mem.seek(start)
                    try: dump = mem.read(end - start)
                    except OSError: continue
                    
                    offset = 0
                    while True:
                        # Procura apenas pela Vida Máxima
                        offset = dump.find(max_hp_bytes, offset)
                        if offset == -1: break
                        
                        # A estrutura é [CurrHP][MaxHP][CurrMana][MaxMana]
                        # Se achamos o MaxHP, o CurrHP está 4 bytes ANTES.
                        # O MaxMana deve estar 8 bytes DEPOIS.
                        if offset >= 4 and offset + 12 <= len(dump):
                            # Confirma se o MaxMana está no lugar certo
                            if dump[offset+8 : offset+12] == max_mana_bytes:
                                # Lê a Vida Atual e a Mana Atual
                                curr_hp = struct.unpack('<i', dump[offset-4 : offset])[0]
                                curr_mana = struct.unpack('<i', dump[offset+4 : offset+8])[0]
                                
                                # Sanidade: A vida atual não pode ser maior que a máxima, nem negativa
                                if 0 <= curr_hp <= self.max_hp and 0 <= curr_mana <= self.max_mana:
                                    return curr_hp, curr_mana
                        offset += 4
        except Exception:
            pass
        return None, None

    def press_key(self, key):
        try:
            env = os.environ.copy()
            env["DISPLAY"] = ":0"
            env["XAUTHORITY"] = "/home/lucasnovaesc/.Xauthority"
            subprocess.Popen(['xdotool', 'key', key], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            print("\n[!] xdotool não instalado.")

    def run(self):
        print("="*50)
        print(" 📡 RADAR STATELESS E HEALER INICIADOS 📡")
        print("="*50)
        print(f"[*] Assinatura Travada: MaxHP={self.max_hp} | MaxMana={self.max_mana}")
        print(f"[*] Limiares: Cura < {self.hp_cura} | Mana Potion < {self.mana_potion}")
        print("="*50)

        while True:
            hp, mana = self.scan_and_read()
            agora = time.time()
            
            if hp is not None and mana is not None:
                print(f"\r[STATUS] HP: {hp:>4}/{self.max_hp} | Mana: {mana:>4}/{self.max_mana}    ", end="")
                
                if hp < self.hp_cura and (agora - self.ultimo_heal) > self.cooldown:
                    print(f"\n[+] CURANDO! HP caiu para {hp}. Tecla {self.tecla_cura}")
                    self.press_key(self.tecla_cura)
                    self.ultimo_heal = agora
                    
                if mana < self.mana_potion and (agora - self.ultima_potion) > self.cooldown:
                    print(f"\n[+] MANA POTION! Mana caiu para {mana}. Tecla {self.tecla_potion}")
                    self.press_key(self.tecla_potion)
                    self.ultima_potion = agora
            else:
                # Opcional: print para debug de objeto perdido
                # print("\r[!] Radar buscando assinatura...                ", end="")
                pass
                
            time.sleep(0.05)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: sudo python3 bot_stateless.py [PID]")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    bot = StatelessHealer(pid, 275, 120)
    
    if bot.map_heap():
        bot.run()