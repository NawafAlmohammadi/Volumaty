"""Serializable settings and keyboard routing, independent of Windows/UI."""
from dataclasses import asdict, dataclass, field
import uuid

MODIFIERS = ('ctrl', 'shift', 'alt', 'windows')
MEDIA_KEYS = {'volume up': 'up', 'volume down': 'down', 'volume mute': 'mute'}
KEY_FIELDS = {'key_up': 'up', 'key_down': 'down', 'key_mute': 'mute'}


def normalize_key(name, scan_code=None):
    media = {-175: 'volume up', -174: 'volume down', -173: 'volume mute'}
    if scan_code in media:
        return media[scan_code]
    name = (name or '').lower().strip()
    aliases = {'left ctrl': 'ctrl', 'right ctrl': 'ctrl', 'control': 'ctrl',
               'left shift': 'shift', 'right shift': 'shift',
               'left alt': 'alt', 'right alt': 'alt', 'alt gr': 'alt',
               'left windows': 'windows', 'right windows': 'windows',
               'win': 'windows', '+': 'plus'}
    return aliases.get(name, name)


def normalize_combo(value):
    parts = [normalize_key(p) for p in str(value or '').split('+') if p.strip()]
    keys = [p for p in parts if p not in MODIFIERS]
    if len(keys) != 1:
        return ''
    return '+'.join([m for m in MODIFIERS if m in parts] + keys)


def format_combo(value):
    return ' + '.join(p.title() for p in value.split('+')) if value else 'Set shortcut'


@dataclass
class Slot:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    app: str = ''
    key_up: str = ''
    key_down: str = ''
    key_mute: str = ''
    knob: bool = False
    all_sessions: bool = True

    @classmethod
    def from_dict(cls, raw):
        raw = raw if isinstance(raw, dict) else {}
        return cls(id=str(raw.get('id') or uuid.uuid4().hex),
                   app=str(raw.get('app') or '') if raw.get('app') != 'No apps found' else '',
                   **{k: normalize_combo(raw.get(k)) for k in KEY_FIELDS},
                   knob=raw.get('knob') is True,
                   all_sessions=raw.get('all_sessions', True) is True)


@dataclass
class Settings:
    slots: list[Slot] = field(default_factory=lambda: [Slot()])
    step: int = 5
    close_to_tray: bool = True

    @classmethod
    def from_dict(cls, data):
        data = data if isinstance(data, dict) else {}
        slots = data.get('slots', [])
        if not isinstance(slots, list):
            slots = []
        try:
            step = max(1, min(20, int(data.get('step', 5))))
        except (ValueError, TypeError):
            step = 5
        result = cls([Slot.from_dict(s) for s in slots[:50]], step,
                     data.get('close_to_tray', True) is True)
        seen = set()
        for slot in result.slots:
            if slot.id in seen:
                slot.id = uuid.uuid4().hex
            seen.add(slot.id)
        return result

    def to_dict(self):
        return {'schema_version': 2, **asdict(self)}


def shortcut_conflict(settings, slot_id, field_name, combo):
    """Return the owner of a shortcut, except the field being edited."""
    combo = normalize_combo(combo)
    for slot in settings.slots:
        for key_field in KEY_FIELDS:
            if slot.id == slot_id and key_field == field_name:
                continue
            if combo and getattr(slot, key_field) == combo:
                return slot.app or 'another card'
    return None


class KeyRouter:
    """Routing only: the hook queues actions; it never calls audio or Tk."""
    def __init__(self):
        self.bindings = {}
        self.knobs = []
        self.held_modifiers = set()
        self.pressed = {}
        self.consumed = set()
        self.paused = False

    def configure(self, settings):
        self.bindings = {}
        knob_targets = {}
        for slot in settings.slots:
            if not slot.app:
                continue
            if slot.knob:
                name = slot.app.lower()
                previous = knob_targets.get(name)
                knob_targets[name] = (slot.app, slot.all_sessions or bool(previous and previous[1]))
            for field_name, action in KEY_FIELDS.items():
                combo = getattr(slot, field_name)
                if combo and combo not in self.bindings:
                    self.bindings[combo] = (slot.app, slot.all_sessions, action)
        self.knobs = list(knob_targets.values())

    def route(self, name, scan_code, down):
        raw_name = (name or '').lower()
        # keyboard's Windows backend reports VK media keys as negative scan codes.
        name = normalize_key(name, scan_code)
        # Key names can change when Shift is released before the main key.
        # Left/right Ctrl share a scan code, so retain the backend's side marker.
        side = ('right' if 'right' in raw_name or raw_name == 'alt gr' else 'left') if name in MODIFIERS else ''
        identity = (scan_code, side)
        if name in MODIFIERS:
            if down:
                self.pressed[identity] = name
            else:
                self.pressed.pop(identity, None)
            self.held_modifiers = {key for key in self.pressed.values() if key in MODIFIERS}
            return [], False
        if not down:
            self.pressed.pop(identity, None)
            was_consumed = identity in self.consumed
            self.consumed.discard(identity)
            return [], was_consumed
        repeated = identity in self.pressed
        self.pressed[identity] = name
        if self.paused:
            return [], False
        if name in MEDIA_KEYS and self.knobs:
            action = MEDIA_KEYS[name]
            self.consumed.add(identity)
            return ([(app, all_sessions, action) for app, all_sessions in self.knobs]
                    if action != 'mute' or not repeated else []), True
        combo = '+'.join([m for m in MODIFIERS if m in self.held_modifiers] + [name])
        binding = self.bindings.get(combo)
        if binding:
            self.consumed.add(identity)
            return [binding] if binding[2] != 'mute' or not repeated else [], True
        return [], False
