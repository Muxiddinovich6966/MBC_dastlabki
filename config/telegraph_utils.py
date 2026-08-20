import os
import requests
from django.conf import settings
import json

def get_telegraph_token():
    token = getattr(settings, 'TELEGRAPH_TOKEN', os.environ.get('TELEGRAPH_TOKEN'))
    if token:
        return token
        
    env_path = os.path.join(settings.BASE_DIR, '.env')
    try:
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                content = f.read()
                if 'TELEGRAPH_TOKEN=' in content:
                    for line in content.split('\n'):
                        if line.startswith('TELEGRAPH_TOKEN='):
                            return line.split('=')[1].strip()
    except:
        pass
        
    try:
        resp = requests.get('https://api.telegra.ph/createAccount?short_name=MBCTadbir&author_name=Bot').json()
        if resp.get('ok'):
            new_token = resp['result']['access_token']
            try:
                with open(env_path, 'a') as f:
                    f.write(f"\nTELEGRAPH_TOKEN={new_token}\n")
            except Exception as e:
                print("Failed to write token to .env:", e)
            return new_token
    except:
        pass
    return ""

def create_telegraph_page(title):
    token = get_telegraph_token()
    if not token:
        return None
    
    url = f"https://api.telegra.ph/createPage"
    content = [{"tag": "p", "children": ["Hozircha hech kim ovoz bermagan"]}]
    payload = {
        'access_token': token,
        'title': title,
        'author_name': 'Bot',
        'content': json.dumps(content),
        'return_content': 'true'
    }
    try:
        r = requests.post(url, data=payload)
        resp = r.json()
        if resp.get('ok'):
            return resp['result']['url']
        else:
            print("[Telegraph API Error]", resp)
    except Exception as e:
        print("Telegraph error:", e)
    return None

def update_event_telegraph(event_id):
    from apps.events.models import Event, UserEvent
    
    try:
        event = Event.objects.get(id=event_id)
        if not event.telegraph_url:
            return
            
        # extract path from url, e.g. https://telegra.ph/Test-06-22 -> Test-06-22
        path = event.telegraph_url.split("/")[-1]
        
        token = get_telegraph_token()
        if not token:
            return
            
        rsvps = UserEvent.objects.filter(event=event).select_related('user')
        
        boraman = []
        balki_borarman = []
        balki_bormasman = []
        bormayman = []
        
        for u in rsvps:
            name = u.user.full_name or u.user.tg_id or "Foydalanuvchi"
            if u.rsvp_choice == 'boraman':
                boraman.append(name)
            elif u.rsvp_choice == 'balki_borarman':
                balki_borarman.append(name)
            elif u.rsvp_choice == 'balki_bormasman':
                balki_bormasman.append(name)
            elif u.rsvp_choice == 'bormayman':
                bormayman.append(name)
                
        content = []
        
        def add_category(title, users):
            content.append({"tag": "h4", "children": [f"{title} ({len(users)})"]})
            if users:
                ul_children = [{"tag": "li", "children": [u]} for u in users]
                content.append({"tag": "ul", "children": ul_children})
            else:
                content.append({"tag": "p", "children": ["Hozircha hech kim yo'q"]})
                
        add_category("✅ Boraman", boraman)
        add_category("🤔 Balki borarman", balki_borarman)
        add_category("😐 Balki bormasman", balki_bormasman)
        add_category("❌ Bormayman", bormayman)
        
        url = f"https://api.telegra.ph/editPage/{path}"
        payload = {
            'access_token': token,
            'title': event.name or "Tadbir",
            'author_name': 'Bot',
            'content': json.dumps(content),
            'return_content': 'true'
        }
        r = requests.post(url, data=payload, timeout=15)
        resp = r.json()
        if not resp.get('ok'):
            print(f"[Telegraph editPage XATO] event_id={event_id}, path={path}, xato={resp}")
        else:
            print(f"[Telegraph] event_id={event_id} sahifasi yangilandi: {resp['result']['url']}")
    except Exception as e:
        print(f"Telegraph Update error (event_id={event_id}):", e)
