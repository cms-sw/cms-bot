import sys


dryRun = False
actions = []
extra_data = ""

if "pytest" not in sys.modules:
    testMode = False
else:
    testMode = True
