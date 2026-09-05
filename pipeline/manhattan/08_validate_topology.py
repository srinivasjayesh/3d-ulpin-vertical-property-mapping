import json

from common import validate_topology

if __name__ == "__main__":
    print(json.dumps(validate_topology(), indent=2))
