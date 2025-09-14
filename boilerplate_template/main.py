import sys
from pathlib import Path

# Add repo root (parent of wa_corps) to sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.driver_session import start_driver
