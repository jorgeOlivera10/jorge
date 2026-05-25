import os

# Env parameters
APP_ENV = os.environ.get("APP_ENV", "development")

SERIES_CONFIG = {
    '6X': {
        'label': 'ZAZ6X',
        'columns': { 'min': 1, 'max': 50 },
        'paths': ['A', 'B'],
        'avenues': {
            'A': { 'row': 10, 'extreme': True },
            'B': { 'row': 95, 'extreme': True }
        },
        'horizontalException': { 'from': 26, 'to': 27, 'distance': 6 }
    },
    '7X': {
        'label': 'ZAZ7X',
        'columns': { 'min': 1, 'max': 34 },
        'paths': ['A', 'B', 'C', 'D'],
        'avenues': {
            'A': { 'row': 10, 'extreme': True },
            'B': { 'row': 37, 'extreme': False },
            'C': { 'row': 67, 'extreme': False },
            'D': { 'row': 95, 'extreme': True }
        },
        'horizontalException': { 'from': 18, 'to': 19, 'distance': 6 }
    }
}

TIER_VALUES = { 3: 10, 4: 15, 5: 15 }
MARGIN = 0.6
ROW_MIN = 11
ROW_MAX = 94
VERTICAL_PER_ROW = 0.3
EXTREME_TRANSITION = 1.2

# Known Inter-Hall distances (metres) by datacenter and path
INTER_HALL_DISTANCES = {
    60: { 'A': 60, 'B': 70 },
    62: { 'A': 51, 'B': 77 },
    72: { 'A': 73, 'D': 74 }
}

def get_known_inter_hall_distance(series_num: int, path: str):
    entry = INTER_HALL_DISTANCES.get(series_num)
    if entry and path in entry:
        return entry[path]
    return None
