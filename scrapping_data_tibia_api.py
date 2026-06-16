import requests
import time


API_URL = "http://127.0.0.1/v4/character/{}"


def calculate_stats(level, vocation):
    vocation = vocation.lower()

    if vocation in ["knight", "elite knight"]:
        hp = 185 + ((level - 8) * 15)
        mana = 90 + ((level - 8) * 5)

    elif vocation in ["paladin", "royal paladin"]:
        hp = 185 + ((level - 8) * 10)
        mana = 90 + ((level - 8) * 15)

    elif vocation in ["druid", "elder druid"]:
        hp = 145 + ((level - 8) * 5)
        mana = 90 + ((level - 8) * 30)

    elif vocation in ["sorcerer", "master sorcerer"]:
        hp = 145 + ((level - 8) * 5)
        mana = 90 + ((level - 8) * 30)

    else:
        hp = None
        mana = None

    return hp, mana


def get_character(name):
    response = requests.get(API_URL.format(name))
    response.raise_for_status()

    data = response.json()

    char = data["character"]["character"]

    level = char["level"]
    vocation = char["vocation"]

    hp_max, mana_max = calculate_stats(level, vocation)

    return {
        "name": char["name"],
        "level": level,
        "vocation": vocation,
        "world": char["world"],
        "health_max": hp_max,
        "mana_max": mana_max,

        # Apenas estimativas
        "health_current": hp_max,
        "mana_current": mana_max
    }


if __name__ == "__main__":

    nickname = "Vegano Chines"

    while True:
        try:
            character = get_character(nickname)

            print("=" * 50)
            print(character)

        except Exception as e:
            print(f"Erro: {e}")

        time.sleep(30)