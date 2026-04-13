#####################################################################################
#####                                                                           #####
#####  https://github.com/netplexflix/User-Restrictions-Label-Manager-for-Plex  #####
#####                                                                           #####
#####################################################################################
from plexapi.myplex import MyPlexAccount
import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote

VERSION= "2026.04.12"

# Configuration
PLEX_TOKEN = "YOUR_PLEX_TOKEN"

def get_users():
    url = f"https://plex.tv/api/users?X-Plex-Token={PLEX_TOKEN}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        users = []
        for user_elem in root.findall('User'):
            users.append({
                'id': user_elem.get('id'),
                'username': (user_elem.get('username') or user_elem.get('title') or '').lower(),
                'title': user_elem.get('title'),
                'moviesFilter': user_elem.get('filterMovies', ''),
                'televisionFilter': user_elem.get('filterTelevision', '')
            })
        return users
    except Exception as e:
        print(f"Error fetching users: {e}")
        return []

def get_labels_action():
    users = get_users()
    print("\nLabel Configuration Report:")
    print("===========================")
    
    for user in users:
        labels = {'Allowed': {}, 'Excluded': {}}
        
        # Process Movies
        movie_filters = user['moviesFilter'].split('&') if user['moviesFilter'] else []
        for f in movie_filters:
            if f.startswith('label='):
                label = f.split('=', 1)[1]
                labels['Allowed'].setdefault('Movies', []).append(label)
            elif f.startswith('label!='):
                label = f.split('!=', 1)[1]
                labels['Excluded'].setdefault('Movies', []).append(label)
        
        # Process TV Shows
        tv_filters = user['televisionFilter'].split('&') if user['televisionFilter'] else []
        for f in tv_filters:
            if f.startswith('label='):
                label = f.split('=', 1)[1]
                labels['Allowed'].setdefault('TV Shows', []).append(label)
            elif f.startswith('label!='):
                label = f.split('!=', 1)[1]
                labels['Excluded'].setdefault('TV Shows', []).append(label)
            
        print(f"\nUser: {user['title']} ({user['username']})")
        for label_type in ['Allowed', 'Excluded']:
            for section in ['Movies', 'TV Shows']:
                if labels[label_type].get(section):
                    print(f"  {label_type} {section}: {', '.join(labels[label_type][section])}")
        
        if not any(labels['Allowed'].values()) and not any(labels['Excluded'].values()):
            print("  No label restrictions configured")

    print("\n===========================")

def update_label(user, label, sections, action="add", label_type="exclude"):
    url = f"https://plex.tv/api/users/{user['id']}?X-Plex-Token={PLEX_TOKEN}"
    params = {}
    changed = False

    for section in sections:
        current_filter = user.get(f'{section}Filter', '')
        filter_dict = parse_filters(current_filter)
        
        key = 'allow' if label_type == 'allow' else 'exclude'
        current_labels = filter_dict.get(key, [])
        
        if action == "add":
            if label not in current_labels:
                current_labels.append(label)
                changed = True
        elif action == "remove":
            if label in current_labels:
                current_labels.remove(label)
                changed = True
        
        if changed:
            filter_dict[key] = current_labels
            param_name = "filterMovies" if section == "movies" else "filterTelevision"
            filter_str = build_filter_string(filter_dict)
            params[param_name] = filter_str

    if not changed:
        return False

    try:
        response = requests.put(url, params=params)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error updating {user['title']}: {e}")
        return False

def parse_filters(filter_str):
    filters = {'allow': [], 'exclude': []}
    if not filter_str:
        return filters
    
    for part in filter_str.split('&'):
        if part.startswith('label='):
            labels = part[6:].split('%2C')
            filters['allow'].extend([label for label in labels if label])
        elif part.startswith('label!='):
            labels = part[7:].split('%2C')
            filters['exclude'].extend([label for label in labels if label])
    
    return filters

def build_filter_string(filter_dict):
    parts = []
    if filter_dict['allow']:
        encoded = quote(','.join(filter_dict['allow']), safe='')
        parts.append(f"label={encoded}")
    if filter_dict['exclude']:
        encoded = quote(','.join(filter_dict['exclude']), safe='')
        parts.append(f"label!={encoded}")
    return '&'.join(parts)

def add_label_action():
    label = input("Enter the label to manage: ").strip()
    if not label:
        print("Error: Label cannot be empty")
        return

    while True:
        label_type = input("Apply to (A)llow only or (E)xclude labels? [A/E]: ").strip().upper()
        if label_type in ('A', 'E'):
            break
        print("Invalid choice. Please enter A or E")
    
    label_type = 'allow' if label_type == 'A' else 'exclude'
    full_type = "Allowed only" if label_type == 'allow' else "Excluded"

    skip_users = []
    skip_input = input("Enter comma-separated usernames to skip (or 'None'): ").strip()
    if skip_input.lower() != 'none':
        skip_users = [u.strip().lower() for u in skip_input.split(',') if u.strip()]

    sections = []
    while not sections:
        sections_input = input("Enter sections to apply (1=Movies, 2=TV Shows): ").strip()
        for s in sections_input.split(','):
            if s.strip() == '1':
                sections.append("movies")
            elif s.strip() == '2':
                sections.append("television")
        
        if not sections:
            print("Error: Please select at least one valid section")

    users = get_users()
    for user in users:
        if user['username'] in skip_users:
            print(f"Skipping user: {user['title']}")
            continue
        
        if update_label(user, label, sections, "add", label_type):
            print(f"Added '{label}' to {full_type} in {user['title']}")
        else:
            print(f"No changes needed for {user['title']}")

def remove_label_action():
    label = input("Enter the label to remove: ").strip()
    if not label:
        print("Error: Label cannot be empty")
        return

    while True:
        removal_type = input("Remove from (A)llow only, (E)xclude, or (B)oth? [A/E/B]: ").strip().upper()
        if removal_type in ('A', 'E', 'B'):
            break
        print("Invalid choice. Please enter A, E, or B")

    users = get_users()
    total_removed = 0
    
    for user in users:
        params = {}
        changed = False

        for section in ["movies", "television"]:
            current_filter = user.get(f'{section}Filter', '')
            filter_dict = parse_filters(current_filter)
            
            modified = False
            if removal_type in ('A', 'B'):
                if label in filter_dict['allow']:
                    filter_dict['allow'].remove(label)
                    modified = True
            if removal_type in ('E', 'B'):
                if label in filter_dict['exclude']:
                    filter_dict['exclude'].remove(label)
                    modified = True
            
            if modified:
                param_name = "filterMovies" if section == "movies" else "filterTelevision"
                params[param_name] = build_filter_string(filter_dict)
                changed = True

        if changed:
            url = f"https://plex.tv/api/users/{user['id']}?X-Plex-Token={PLEX_TOKEN}"
            try:
                response = requests.put(url, params=params)
                response.raise_for_status()
                print(f"Removed '{label}' from {user['title']}")
                total_removed += 1
            except Exception as e:
                print(f"Error updating {user['title']}: {e}")
        else:
            print(f"No '{label}' found for {user['title']}")

    print(f"\nOperation complete. Removed from {total_removed} users.")

def main():
    print("Plex Label Manager")
    print("------------------")
    
    while True:
        action = input("\nChoose action (ADD/REMOVE/GET/EXIT): ").strip().upper()
        if action == 'EXIT':
            break
        if action == 'ADD':
            add_label_action()
        elif action == 'REMOVE':
            remove_label_action()
        elif action == 'GET':
            get_labels_action()
        else:
            print("Invalid action. Please choose ADD, REMOVE, GET, or EXIT.")

if __name__ == '__main__':
    main()