import sys
from pathlib import Path

# The pipeline modules import each other flatly (`import common`), matching how
# they are run: `python pipeline/etl.py`. Put the package dir on the path so
# pytest resolves them the same way.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
