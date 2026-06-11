import os
import struct
import time
import sys
import subprocess

class TibiaHealer:
    def __init__(self, pid, address):
        self.pid = pid
        self.target_address = address
        self.mem_file = None
        
        # --- CONFIGURAÇÕES DE CURA ---
        self.hp_cura_leve = 200     # Se a vida cair abaixo disso, usa Magia de Cura
        self.tecla_cura_leve = "F1" # Tecla da magia (Ex: Exura)
        self.cooldown_cura = 1.0    # Espera 1 segundo antes de tentar curar de novo
        
        self.mana_potion = 50       # Se a mana cair abaixo disso, usa Potion
        self.tecla_potion = "F2"    # Tecla da Mana Potion
        self.cooldown_potion = 1.0  # Espera 1 segundo para usar outra potion
        
        # Temporizadores internos
        self.ultimo_heal = 0
        self.ultima_potion = 0

    def read_vitals(self):
        if not self.mem_file:
            try:
                self.mem_file = open(f"/proc/{self.pid}/mem", "rb")
            except PermissionError:
                print("[!] Execute como root (sudo).")
                sys.exit(1)
                
        try:
            self.mem_file.seek(self.target_address)
            hp, max_hp, mana, max_mana = struct.unpack('<iiii', self.mem_file.read(16))
            return hp, max_hp, mana, max_mana
        except Exception:
            return None

    def press_key(self, key):
        """Usa o xdotool para injetar a tecla no sistema do Fedora."""
        try:
            # Como o script roda como root (sudo), precisamos especificar o DISPLAY 
            # e o usuário logado para o xdotool achar a janela do servidor X11/Wayland
            env = os.environ.copy()
            env["DISPLAY"] = ":0"
            env["XAUTHORITY"] = "/home/lucasnovaesc/.Xauthority"
            
            # O comando xdotool envia a tecla virtualmente
            subprocess.Popen(['xdotool', 'key', key], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except FileNotFoundError:
            print("\n[!] AVISO: 'xdotool' não encontrado! Instale com: sudo dnf install xdotool")
            return False

    def run(self):
        print("="*50)
        print(" 💊 AUTO-HEALER INICIADO 💊")
        print("="*50)
        print(f"[*] Lendo núcleo lógico em: {hex(self.target_address)}")
        print(f"[*] Regras:")
        print(f"    -> HP < {self.hp_cura_leve}  = Aperta {self.tecla_cura_leve}")
        print(f"    -> MP < {self.mana_potion}   = Aperta {self.tecla_potion}")
        print("="*50)

        try:
            while True:
                status = self.read_vitals()
                if not status:
                    print("\r[!] Falha na leitura da memória. O jogo fechou?  ", end="")
                    time.sleep(1)
                    continue
                    
                hp, max_hp, mana, max_mana = status
                agora = time.time()
                
                # --- LÓGICA DE CURA (HP) ---
                if hp < self.hp_cura_leve and (agora - self.ultimo_heal) > self.cooldown_cura:
                    print(f"\n[+] HP Crítico ({hp}/{max_hp})! Injetando tecla {self.tecla_cura_leve}...")
                    self.press_key(self.tecla_cura_leve)
                    self.ultimo_heal = agora
                    
                # --- LÓGICA DE MANA (MP) ---
                if mana < self.mana_potion and (agora - self.ultima_potion) > self.cooldown_potion:
                    print(f"\n[+] Mana Crítica ({mana}/{max_mana})! Injetando tecla {self.tecla_potion}...")
                    self.press_key(self.tecla_potion)
                    self.ultima_potion = agora
                    
                # Display no terminal
                print(f"\r[STATUS] HP: {hp:>4} | Mana: {mana:>4}    ", end="")
                
                # Loop a 100hz (10ms) para reação extremamente rápida
                time.sleep(0.01) 
                
        except KeyboardInterrupt:
            print("\n[*] Bot pausado com sucesso.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: sudo python3 bot_healer.py [PID]")
        sys.exit(1)
        
    pid = int(sys.argv[1])
    
    # O endereço persistente isolado nesta sessão
    ENDERECO_RAIZ = 0x56453c1906a8 
    
    bot = TibiaHealer(pid, ENDERECO_RAIZ)
    bot.run()