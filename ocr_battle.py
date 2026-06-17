import time
import cv2
import numpy as np
import mss


class VisionCore:
    def __init__(self):
        self.sct = mss.MSS()

        # Estado Visual
        self.battle_x = None
        self.battle_y = None
        self.ring_x = None
        self.ring_y = None

        # Battle List
        self.BATTLE_OFFSET_X = 5
        self.BATTLE_OFFSET_Y = 25
        self.BATTLE_ROW_HEIGHT = 22
        self.BATTLE_MAX_ROWS = 8

        # Ring
        self.RING_OFFSET_X = 0
        self.RING_OFFSET_Y = 30

    def find_anchors(self):
        print("[*] Rodando Busca de Âncoras (Template Matching)...")

        monitor = self.sct.monitors[1]
        scr = np.array(self.sct.grab(monitor))

        # CORRIGIDO
        tela_gray = cv2.cvtColor(scr, cv2.COLOR_BGRA2GRAY)

        try:
            template_battle = cv2.imread(
                "battle_anchor.png",
                cv2.IMREAD_GRAYSCALE
            )

            if template_battle is None:
                print("[!] battle_anchor.png não encontrado.")
                return False

            res_b = cv2.matchTemplate(
                tela_gray,
                template_battle,
                cv2.TM_CCOEFF_NORMED
            )

            _, max_val_b, _, max_loc_b = cv2.minMaxLoc(res_b)

            if max_val_b > 0.80:
                self.battle_x, self.battle_y = max_loc_b
                print(
                    f"[+] Battle List ancorada em "
                    f"{self.battle_x}, {self.battle_y} "
                    f"(confiança {max_val_b:.2f})"
                )
            else:
                print(
                    f"[-] battle_anchor.png não encontrado "
                    f"(confiança {max_val_b:.2f})"
                )

            template_ring = cv2.imread(
                "ring_anchor.png",
                cv2.IMREAD_GRAYSCALE
            )

            if template_ring is None:
                print("[!] ring_anchor.png não encontrado.")
                return False

            res_r = cv2.matchTemplate(
                tela_gray,
                template_ring,
                cv2.TM_CCOEFF_NORMED
            )

            _, max_val_r, _, max_loc_r = cv2.minMaxLoc(res_r)

            if max_val_r > 0.80:
                self.ring_x, self.ring_y = max_loc_r
                print(
                    f"[+] Ring ancorado em "
                    f"{self.ring_x}, {self.ring_y} "
                    f"(confiança {max_val_r:.2f})"
                )
            else:
                print(
                    f"[-] ring_anchor.png não encontrado "
                    f"(confiança {max_val_r:.2f})"
                )

            return (
                self.battle_x is not None and
                self.ring_x is not None
            )

        except Exception as e:
            print(f"[!] Erro no template matching: {e}")
            return False

    def check_watchdog(self):
        if self.battle_x is None:
            return False

        return True

    def read_battle_list(self):
        if self.battle_x is None:
            return 0

        altura_total = (
            self.BATTLE_ROW_HEIGHT *
            self.BATTLE_MAX_ROWS
        )

        roi = {
            "top": self.battle_y + self.BATTLE_OFFSET_Y,
            "left": self.battle_x + self.BATTLE_OFFSET_X,
            "width": 100,
            "height": altura_total
        }

        img = np.array(self.sct.grab(roi))

        monstros_vistos = 0

        for row in range(self.BATTLE_MAX_ROWS):

            y_pixel = (
                row *
                self.BATTLE_ROW_HEIGHT +
                5
            )

            linha_pixels = img[
                y_pixel:y_pixel + 1,
                0:100
            ]

            if linha_pixels.size == 0:
                continue

            b, g, r, a = cv2.split(linha_pixels)

            red_pixels = np.sum(
                (r > 150) &
                (g < 50) &
                (b < 50)
            )

            green_pixels = np.sum(
                (g > 150) &
                (r < 50) &
                (b < 50)
            )

            yellow_pixels = np.sum(
                (r > 150) &
                (g > 150) &
                (b < 50)
            )

            if (
                red_pixels > 5 or
                green_pixels > 5 or
                yellow_pixels > 5
            ):
                monstros_vistos += 1

        return monstros_vistos

    def check_ring(self):
        if self.ring_x is None:
            return False

        roi = {
            "top": self.ring_y + self.RING_OFFSET_Y,
            "left": self.ring_x + self.RING_OFFSET_X,
            "width": 32,
            "height": 32
        }

        img = np.array(self.sct.grab(roi))

        std_dev = np.std(img)

        return std_dev > 15.0

    def run(self):
        print("=" * 60)
        print(" 👁️ VISION CORE - TESTE UNITÁRIO ")
        print("=" * 60)

        if not self.find_anchors():
            print(
                "\n[!] Ajuste as imagens "
                "battle_anchor.png e ring_anchor.png"
            )
            return

        print("\n[*] Motores visuais engatados.")

        try:
            while True:

                if not self.check_watchdog():
                    print(
                        "\n[!] Watchdog falhou. "
                        "Reancorando..."
                    )

                    self.find_anchors()
                    continue

                inicio = time.perf_counter()

                qtd_monstros = self.read_battle_list()
                anel_on = self.check_ring()

                tempo_ms = (
                    time.perf_counter() -
                    inicio
                ) * 1000

                anel_txt = (
                    "\033[92mEQUIPADO\033[0m"
                    if anel_on
                    else
                    "\033[91mVAZIO\033[0m"
                )

                print(
                    f"\r\033[K"
                    f"[Latência: {tempo_ms:.2f}ms] "
                    f"Monstros: {qtd_monstros}/8 | "
                    f"Anel: {anel_txt}",
                    end=""
                )

                time.sleep(0.10)

        except KeyboardInterrupt:
            print("\n\n[*] Encerrado.")

        except Exception as e:
            print(f"\n[!] Erro fatal: {e}")


if __name__ == "__main__":
    VisionCore().run()