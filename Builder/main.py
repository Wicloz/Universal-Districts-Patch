from tools import ParadoxFile
from pathlib import Path

GAME_FOLDER = Path(r'D:\Game Libraries\Steam\steamapps\common\Stellaris')
WORKSHOP_FOLDER = Path(r'D:\Game Libraries\Steam\steamapps\workshop\content\281990')

if __name__ == '__main__':
    vanilla = ParadoxFile(GAME_FOLDER / 'common' / 'districts' / '00_urban_districts.txt')
    vanilla.print()
    modded = ParadoxFile(WORKSHOP_FOLDER / '1100284147' / 'common' / 'districts' / '00_urban_districts.txt')
    modded.print()
