import json

from common import validate_vertical_ids

if __name__ == "__main__":
    print(json.dumps(validate_vertical_ids(), indent=2))
