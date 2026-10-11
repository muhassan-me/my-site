import json
from pathlib import Path

data_dir = Path('data')

# Load latest.json
latest_file = data_dir / 'latest.json'
with open(latest_file, 'r', encoding='utf-8') as f:
    latest_old = json.load(f)

# Convert latest.json
countries = {"Egypt": []}
for loc in latest_old['locations']:
    countries["Egypt"].append({
        'name': loc['name'],
        'participants': loc['participants'],
        'virtual': loc['virtual'],
        'inPerson': loc['inPerson'],
        'accepting': loc['accepting']
    })

latest_new = {
    'capturedAt': latest_old['capturedAt'],
    'countries': countries
}

# Write latest.json
with open(latest_file, 'w', encoding='utf-8') as f:
    json.dump(latest_new, f, indent=2)

print('Updated latest.json')

# Load history.json
history_file = data_dir / 'history.json'
with open(history_file, 'r', encoding='utf-8') as f:
    history_old = json.load(f)

# Convert each snapshot in history
history_new = []
for snapshot in history_old:
    countries = {"Egypt": []}
    for loc in snapshot['locations']:
        countries["Egypt"].append({
            'name': loc['name'],
            'participants': loc['participants'],
            'virtual': loc['virtual'],
            'inPerson': loc['inPerson'],
            'accepting': loc['accepting']
        })
    history_new.append({
        'timestamp': snapshot['timestamp'],
        'countries': countries
    })

# Write history.json
with open(history_file, 'w', encoding='utf-8') as f:
    json.dump(history_new, f, indent=2)

print('Updated history.json')

# Create regions.json from governorates.json
gov_file = data_dir / 'governorates.json'
with open(gov_file, 'r', encoding='utf-8') as f:
    gov_data = json.load(f)

regions_data = {"Egypt": gov_data}

regions_file = data_dir / 'regions.json'
with open(regions_file, 'w', encoding='utf-8') as f:
    json.dump(regions_data, f, indent=2)

print('Created regions.json')