"""Volumaty desktop UI. Widgets and mutable settings belong to the Tk thread."""
from pathlib import Path
from queue import Empty
import logging
import os
import sys
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageDraw
from .models import Slot, KEY_FIELDS, format_combo, normalize_combo, shortcut_conflict
from .windows import desktop_path, create_shortcut
from . import __version__

log = logging.getLogger(__name__)
BG = '#10151C'
SIDE = '#151C25'
CARD = '#1B2430'
INSET = '#121A23'
BORDER = '#2A3746'
TEXT = '#F2F6FA'
MUTED = '#94A6BA'
ACCENT = '#57D7BE'
HOVER = '#7EE5D1'
DANGER = '#FF9B9B'


def label(parent, text, size=13, color=TEXT, bold=False, **kw):
    return ctk.CTkLabel(parent, text=text, text_color=color,
                        font=ctk.CTkFont(family='Segoe UI', size=size, weight='bold' if bold else 'normal'), **kw)


def button(parent, text, command, primary=False, **kw):
    return ctk.CTkButton(parent, text=text, command=command, height=36, corner_radius=9,
                        fg_color=ACCENT if primary else BORDER,
                        hover_color=HOVER if primary else '#354558',
                        text_color=BG if primary else TEXT,
                        font=ctk.CTkFont(family='Segoe UI', size=12, weight='bold'), **kw)


def tray_image():
    image = Image.new('RGBA', (64, 64), BG)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((2, 2, 62, 62), radius=16, fill=ACCENT)
    draw.ellipse((13, 13, 51, 51), fill=BG)
    draw.ellipse((23, 23, 41, 41), fill=ACCENT)
    draw.line((32, 9, 32, 22), fill=BG, width=5)
    return image


class AppCard(ctk.CTkFrame):
    def __init__(self, parent, owner, slot):
        super().__init__(parent, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=15)
        self.owner, self.slot = owner, slot
        self.key_buttons = {}
        self.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(self, fg_color='transparent')
        top.grid(row=0, column=0, sticky='ew', padx=20, pady=(17, 10))
        top.grid_columnconfigure(1, weight=1)
        label(top, 'APP', size=11, color=ACCENT, bold=True, width=48,
              fg_color=INSET, corner_radius=8, height=40).grid(row=0, column=0, rowspan=2, padx=(0, 12))
        self.title_label = label(top, self.display_name(), size=17, bold=True, anchor='w')
        self.title_label.grid(row=0, column=1, sticky='ew')
        self.state_label = label(top, 'Waiting for audio session', size=11, color=MUTED, anchor='w')
        self.state_label.grid(row=1, column=1, sticky='ew')
        button(top, 'Remove', lambda: owner.delete_slot(slot.id), width=74).grid(row=0, column=2, rowspan=2)

        picker_row = ctk.CTkFrame(self, fg_color='transparent')
        picker_row.grid(row=1, column=0, sticky='ew', padx=20, pady=(0, 14))
        picker_row.grid_columnconfigure(0, weight=1)
        self.picker = ctk.CTkComboBox(picker_row, values=owner.app_names(slot), command=self.choose_app,
                                    height=36, corner_radius=8, border_color=BORDER,
                                    fg_color=INSET, button_color=BORDER, button_hover_color='#354558',
                                    dropdown_fg_color=CARD, dropdown_hover_color=BORDER,
                                    text_color=TEXT, state='normal')
        self.picker.set(slot.app)
        self.picker.grid(row=0, column=0, sticky='ew')
        self.picker.bind('<Return>', lambda _e: self.choose_app(self.picker.get()))
        self.picker.bind('<FocusOut>', lambda _e: self.choose_app(self.picker.get()))

        volume_row = ctk.CTkFrame(self, fg_color=INSET, corner_radius=10)
        volume_row.grid(row=2, column=0, sticky='ew', padx=20, pady=(0, 14))
        volume_row.grid_columnconfigure(0, weight=1)
        self.percent = label(volume_row, '--', size=28, color=ACCENT, bold=True, anchor='w')
        self.percent.grid(row=0, column=0, sticky='ew', padx=16, pady=(9, 0))
        self.mute_button = button(volume_row, 'Mute', self.mute, width=72)
        self.mute_button.grid(row=0, column=1, padx=14, pady=(10, 0))
        self.slider = ctk.CTkSlider(volume_row, from_=0, to=100, number_of_steps=100,
                                   command=self.set_volume, progress_color=ACCENT,
                                   button_color=ACCENT, button_hover_color=HOVER, fg_color=BORDER, height=20)
        self.slider.set(0)
        self.slider.grid(row=1, column=0, columnspan=2, sticky='ew', padx=14, pady=(5, 12))
        self.pending_until = 0

        options = ctk.CTkFrame(self, fg_color='transparent')
        options.grid(row=3, column=0, sticky='ew', padx=20, pady=(0, 12))
        options.grid_columnconfigure(0, weight=1)
        self.knob = ctk.CTkSwitch(options, text='Use keyboard knob', command=self.change_options,
                                  progress_color=ACCENT, button_color=TEXT,
                                  font=ctk.CTkFont(size=12), text_color=TEXT, switch_width=34, switch_height=18)
        self.knob.grid(row=0, column=0, sticky='w', pady=4)
        self.all_sessions = ctk.CTkSwitch(options, text='All audio sessions', command=self.change_options,
                                          progress_color=ACCENT, button_color=TEXT,
                                          font=ctk.CTkFont(size=12), text_color=TEXT, switch_width=34, switch_height=18)
        self.all_sessions.grid(row=1, column=0, sticky='w', pady=4)
        if slot.knob:
            self.knob.select()
        if slot.all_sessions:
            self.all_sessions.select()

        shortcuts = ctk.CTkFrame(self, fg_color='transparent')
        shortcuts.grid(row=4, column=0, sticky='ew', padx=20, pady=(0, 16))
        shortcuts.grid_columnconfigure(1, weight=1)
        for row, (field, caption) in enumerate([('key_up', 'Volume up'), ('key_down', 'Volume down'), ('key_mute', 'Mute')]):
            label(shortcuts, caption, size=12, color=MUTED, width=95, anchor='w').grid(row=row, column=0, sticky='w', pady=3)
            btn = button(shortcuts, format_combo(getattr(slot, field)), lambda key=field: owner.capture(self, key), width=120)
            btn.grid(row=row, column=1, sticky='ew', pady=3)
            self.key_buttons[field] = btn
            button(shortcuts, 'x', lambda key=field: self.clear_key(key), width=28).grid(row=row, column=2, padx=(6, 0), pady=3)

    def display_name(self):
        return self.slot.app.removesuffix('.exe') or 'Choose an application'

    def choose_app(self, name):
        name = name.strip()
        if name == self.slot.app:
            return
        if name and not name.lower().endswith('.exe'):
            self.owner.notify('Enter a process name ending in .exe, such as Discord.exe.', error=True)
            self.picker.set(self.slot.app)
            return
        self.slot.app = name
        self.title_label.configure(text=self.display_name())
        self.owner.changed()
        self.update_audio(self.owner.snapshot.get(name.lower()))

    def change_options(self):
        self.slot.knob = bool(self.knob.get())
        self.slot.all_sessions = bool(self.all_sessions.get())
        self.owner.changed()

    def clear_key(self, field):
        if self.owner.capture_target:
            self.owner.cancel_capture()
        setattr(self.slot, field, '')
        self.key_buttons[field].configure(text='Set shortcut', text_color=TEXT)
        self.owner.changed()

    def set_volume(self, value):
        import time
        self.pending_until = time.monotonic() + 0.3
        self.percent.configure(text=f'{round(value)}%')
        if self.slot.app:
            self.owner.audio.submit(self.slot.app, self.slot.all_sessions, 'set', value / 100)

    def mute(self):
        self.owner.audio.submit(self.slot.app, self.slot.all_sessions, 'mute')

    def update_audio(self, state):
        import time
        available = state is not None
        self.slider.configure(state='normal' if available else 'disabled')
        self.mute_button.configure(state='normal' if available else 'disabled')
        if not state:
            self.state_label.configure(text='Play audio to connect' if self.slot.app else 'Select or type a process name', text_color=MUTED)
            self.percent.configure(text='--', text_color=MUTED)
            self.slider.set(0)
            return
        muted = state['muted']
        count = state['sessions']
        self.state_label.configure(text=('Muted' if muted else 'Connected') + f'  /  {count} audio session' + ('s' if count != 1 else ''),
                                   text_color=MUTED if muted else ACCENT)
        self.mute_button.configure(text='Unmute' if muted else 'Mute')
        if time.monotonic() > self.pending_until:
            self.percent.configure(text=f"{round(state['volume'] * 100)}%", text_color=MUTED if muted else ACCENT)
            self.slider.set(state['volume'] * 100)


class VolumatyWindow(ctk.CTk):
    def __init__(self, store, settings, audio, keyboard, messages, startup, instance, background=False, isolated=False):
        ctk.set_appearance_mode('dark')
        super().__init__()
        self.store, self.settings, self.audio, self.keyboard = store, settings, audio, keyboard
        self.messages, self.startup, self.instance = messages, startup, instance
        self.isolated = isolated
        self.snapshot = {}
        self.cards = []
        self.capture_target = None
        self.save_job = None
        self.quitting = False
        self.tray = None
        self.page = 'mixer'
        self._last_names = None
        self._status_generation = 0
        self.keyboard_ready = False
        self.title('Volumaty')
        self.geometry('1080x820')
        self.minsize(880, 680)
        self.configure(fg_color=BG)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        icon = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1])) / 'assets' / 'icon.ico'
        if icon.exists():
            self.iconbitmap(str(icon))
        self._build_shell()
        self.show_mixer()
        self.protocol('WM_DELETE_WINDOW', self.close_window)
        self.report_callback_exception = self.report_error
        self.after(50, self.pump)
        self.start_tray()
        if store.notice:
            self.notify(store.notice, error=True)
        if background and self.tray:
            self.withdraw()

    def _build_shell(self):
        sidebar = ctk.CTkFrame(self, width=204, fg_color=SIDE, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky='nsew')
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(6, weight=1)
        label(sidebar, 'V', size=30, color=BG, bold=True, fg_color=ACCENT, corner_radius=14,
              width=52, height=52).grid(row=0, column=0, sticky='w', padx=24, pady=(28, 13))
        label(sidebar, 'Volumaty', size=25, bold=True, anchor='w').grid(row=1, column=0, sticky='ew', padx=24)
        label(sidebar, 'Your sound. Your control.', size=11, color=MUTED, anchor='w').grid(row=2, column=0, sticky='ew', padx=24, pady=(0, 32))
        self.mixer_nav = button(sidebar, 'Volume mixer', self.show_mixer, width=156)
        self.mixer_nav.grid(row=3, column=0, sticky='ew', padx=18, pady=5)
        self.settings_nav = button(sidebar, 'Settings', self.show_settings, width=156)
        self.settings_nav.grid(row=4, column=0, sticky='ew', padx=18, pady=5)
        self.pause_button = button(sidebar, 'Pause controls', self.toggle_pause, width=156)
        self.pause_button.grid(row=5, column=0, sticky='ew', padx=18, pady=(20, 5))
        info = ctk.CTkFrame(sidebar, fg_color=INSET, corner_radius=12)
        info.grid(row=7, column=0, sticky='ew', padx=18, pady=(18, 10))
        self.hook_label = label(info, 'Connecting...', size=12, color=MUTED, anchor='w')
        self.hook_label.pack(fill='x', padx=12, pady=(12, 4))
        self.knob_label = label(info, '0 knob targets', size=11, color=MUTED, anchor='w')
        self.knob_label.pack(fill='x', padx=12, pady=(0, 12))
        label(sidebar, f'WINDOWS  /  v{__version__}', size=10, color=MUTED, anchor='w').grid(row=8, column=0, sticky='ew', padx=24, pady=(8, 22))

        self.main = ctk.CTkFrame(self, fg_color='transparent', corner_radius=0)
        self.main.grid(row=0, column=1, sticky='nsew')
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(1, weight=1)
        self.header = ctk.CTkFrame(self.main, fg_color='transparent')
        self.header.grid(row=0, column=0, sticky='ew', padx=28, pady=(26, 18))
        self.header.grid_columnconfigure(0, weight=1)
        self.page_title = label(self.header, 'Volume mixer', size=28, bold=True, anchor='w')
        self.page_title.grid(row=0, column=0, sticky='ew')
        self.page_desc = label(self.header, 'One knob. The apps you choose.', size=13, color=MUTED, anchor='w')
        self.page_desc.grid(row=1, column=0, sticky='ew', pady=(3, 0))
        self.refresh_button = button(self.header, 'Refresh apps', self.audio.refresh, width=110)
        self.refresh_button.grid(row=0, column=1, rowspan=2, padx=(10, 8))
        self.add_button = button(self.header, '+ Add app', self.add_slot, primary=True, width=105)
        self.add_button.grid(row=0, column=2, rowspan=2)
        self.content = ctk.CTkScrollableFrame(self.main, fg_color='transparent', corner_radius=0,
                                             scrollbar_button_color=BORDER)
        self.content.grid(row=1, column=0, sticky='nsew', padx=(22, 20))
        for col in (0, 1):
            self.content.grid_columnconfigure(col, weight=1, uniform='cards')
        footer = ctk.CTkFrame(self.main, fg_color='transparent')
        footer.grid(row=2, column=0, sticky='ew', padx=28, pady=(14, 20))
        footer.grid_columnconfigure(0, weight=1)
        self.status_label = label(footer, 'Ready  /  Changes save automatically', size=11, color=MUTED,
                                  anchor='w', wraplength=540, justify='left')
        self.status_label.grid(row=0, column=0, sticky='ew')
        button(footer, 'Quit', self.quit_app, width=62).grid(row=0, column=1, padx=(8, 0))

    def clear_content(self):
        self.cancel_capture()
        self.cards.clear()
        for child in self.content.winfo_children():
            child.destroy()

    def show_mixer(self):
        self.page = 'mixer'
        self.clear_content()
        self.page_title.configure(text='Volume mixer')
        self.page_desc.configure(text='One knob. The apps you choose.')
        self.mixer_nav.configure(fg_color=BORDER, text_color=ACCENT)
        self.settings_nav.configure(fg_color=SIDE, text_color=MUTED)
        self.add_button.grid()
        self.refresh_button.grid()
        help_frame = ctk.CTkFrame(self.content, fg_color=SIDE, border_color=BORDER, border_width=1, corner_radius=12)
        help_frame.grid(row=0, column=0, columnspan=2, sticky='ew', padx=6, pady=(0, 16))
        label(help_frame, 'MAKE YOUR KEYBOARD KNOB WORK FOR YOU', size=11, color=ACCENT, bold=True,
              anchor='w').pack(fill='x', padx=17, pady=(13, 3))
        label(help_frame, 'Enable the knob on a card, then turn it to adjust that app.\nYou can control several apps together or assign separate shortcuts.',
              size=12, color=MUTED, justify='left', anchor='w').pack(fill='x', padx=17, pady=(0, 13))
        if not self.settings.slots:
            label(self.content, 'Build your personal mixer', size=23, bold=True).grid(row=1, column=0, columnspan=2, pady=(65, 8))
            label(self.content, 'Add an app, play some audio, then enable the keyboard knob.', color=MUTED).grid(row=2, column=0, columnspan=2)
            button(self.content, '+ Add your first app', self.add_slot, primary=True, width=190).grid(row=3, column=0, columnspan=2, pady=22)
        for i, slot in enumerate(self.settings.slots):
            card = AppCard(self.content, self, slot)
            card.grid(row=1 + i // 2, column=i % 2, sticky='new', padx=6, pady=(0, 12))
            card.update_audio(self.snapshot.get(slot.app.lower()))
            self.cards.append(card)
        self.update_counts()

    def app_names(self, slot):
        names = {s['name'] for s in self.snapshot.values()}
        names.update(s.app for s in self.settings.slots if s.app)
        return sorted(names, key=str.lower) or ['']

    def add_slot(self):
        if len(self.settings.slots) >= 50:
            self.notify('The mixer supports up to 50 cards.', error=True)
            return
        self.settings.slots.append(Slot())
        self.changed()
        self.show_mixer()

    def delete_slot(self, slot_id):
        self.settings.slots = [s for s in self.settings.slots if s.id != slot_id]
        self.changed()
        self.show_mixer()

    def capture(self, card, field):
        if not self.keyboard_ready:
            self.notify('Keyboard hook is unavailable. Restart Volumaty to try again.', error=True)
            return
        self.cancel_capture()
        token = (card.slot.id, field)
        self.capture_target = (card, field, token)
        card.key_buttons[field].configure(text='Press keys...', text_color=ACCENT)
        self.keyboard.begin_capture(token)
        self.notify('Press a key or combination. Esc cancels. Capture ends after 12 seconds.')

    def cancel_capture(self):
        if self.capture_target:
            card, field, _ = self.capture_target
            if card.winfo_exists():
                card.key_buttons[field].configure(text=format_combo(getattr(card.slot, field)), text_color=TEXT)
            self.capture_target = None
        self.keyboard.cancel_capture()

    def finish_capture(self, payload):
        token, combo = payload
        if not self.capture_target or token != self.capture_target[2]:
            return
        card, field, _ = self.capture_target
        self.cancel_capture()
        if not combo:
            self.notify('Shortcut capture cancelled.')
            return
        combo = normalize_combo(combo)
        if not combo:
            self.notify('That key cannot be assigned. Try another key.', error=True)
            return
        owner = shortcut_conflict(self.settings, card.slot.id, field, combo)
        if owner:
            self.notify(f'This shortcut is already assigned to {owner}.', error=True)
            return
        setattr(card.slot, field, combo)
        card.key_buttons[field].configure(text=format_combo(combo), text_color=TEXT)
        self.changed()

    def changed(self):
        self.keyboard.configure(self.settings)
        self.update_counts()
        self.notify('Saving changes...')
        if self.save_job:
            self.after_cancel(self.save_job)
        self.save_job = self.after(350, self.save_settings)

    def save_settings(self):
        self.save_job = None
        try:
            self.store.save(self.settings)
            self.notify('Saved  /  Changes apply immediately')
            return True
        except OSError:
            log.exception('Could not save settings')
            self.notify('Could not save settings. Check your data folder permissions.', error=True)
            return False

    def notify(self, text, error=False):
        self._status_generation += 1
        self.status_label.configure(text=text, text_color=DANGER if error else MUTED)

    def update_counts(self):
        count = sum(s.knob and bool(s.app) for s in self.settings.slots)
        self.knob_label.configure(text=f'{count} knob target' + ('s' if count != 1 else ''))

    def toggle_pause(self):
        paused = not self.keyboard.router.paused
        self.keyboard.pause(paused)
        self.pause_button.configure(text='Resume controls' if paused else 'Pause controls')
        self.hook_label.configure(text='Controls paused' if paused else ('Controls active' if self.keyboard_ready else 'Hook unavailable'),
                                  text_color=MUTED if paused else ACCENT)
        self.notify('Keyboard knob and shortcuts are paused.' if paused else 'Keyboard controls resumed.')

    def setting_panel(self, row, title, desc):
        frame = ctk.CTkFrame(self.content, fg_color=CARD, border_color=BORDER, border_width=1, corner_radius=14)
        frame.grid(row=row, column=0, columnspan=2, sticky='ew', padx=6, pady=(0, 14))
        label(frame, title, size=17, bold=True, anchor='w').pack(fill='x', padx=20, pady=(17, 3))
        label(frame, desc, size=12, color=MUTED, anchor='w', justify='left').pack(fill='x', padx=20, pady=(0, 13))
        return frame

    def show_settings(self):
        self.page = 'settings'
        self.clear_content()
        self.page_title.configure(text='Settings')
        self.page_desc.configure(text='Set it once. Make it yours.')
        self.mixer_nav.configure(fg_color=SIDE, text_color=MUTED)
        self.settings_nav.configure(fg_color=BORDER, text_color=ACCENT)
        self.add_button.grid_remove()
        self.refresh_button.grid_remove()
        startup_frame = self.setting_panel(0, 'Start with Windows', 'Launch quietly in the system tray when you sign in.')
        self.startup_switch = ctk.CTkSwitch(startup_frame, text='Run Volumaty at sign-in', command=self.toggle_startup,
                                           progress_color=ACCENT, text_color=TEXT)
        self.startup_switch.pack(anchor='w', padx=20, pady=(0, 10))
        self.startup_status_label = label(startup_frame, '', size=12, color=MUTED, anchor='w', justify='left')
        self.startup_status_label.pack(fill='x', padx=20, pady=(0, 16))
        self.repair_button = button(startup_frame, 'Update startup path', self.repair_startup, width=170)
        if self.isolated:
            self.startup_switch.configure(state='disabled')
            self.startup_status_label.configure(text='Preview profile: startup changes are disabled.')
        else:
            self.refresh_startup()

        behavior = self.setting_panel(1, 'Keyboard & background', 'Your media keys work normally when no knob target is enabled.')
        step_row = ctk.CTkFrame(behavior, fg_color='transparent')
        step_row.pack(fill='x', padx=20, pady=(0, 10))
        label(step_row, 'Volume change per tick', color=MUTED).pack(side='left')
        self.step_label = label(step_row, f'{self.settings.step}%', color=ACCENT, bold=True, width=45)
        self.step_label.pack(side='right')
        self.step_slider = ctk.CTkSlider(behavior, from_=1, to=20, number_of_steps=19, progress_color=ACCENT,
                                       button_color=ACCENT, command=self.change_step)
        self.step_slider.set(self.settings.step)
        self.step_slider.pack(fill='x', padx=20, pady=(0, 18))
        self.close_switch = ctk.CTkSwitch(behavior, text='Close window to system tray', command=self.change_close,
                                         progress_color=ACCENT, text_color=TEXT)
        if self.settings.close_to_tray:
            self.close_switch.select()
        self.close_switch.pack(anchor='w', padx=20, pady=(0, 18))

        transfer = self.setting_panel(2, 'Backup & restore', 'Take your app cards and shortcuts with you. Imports keep a backup of your current settings.')
        transfer_row = ctk.CTkFrame(transfer, fg_color='transparent')
        transfer_row.pack(fill='x', padx=20, pady=(0, 17))
        button(transfer_row, 'Export settings', self.export_settings, width=145).pack(side='left', padx=(0, 10))
        button(transfer_row, 'Import settings', self.import_settings, width=145).pack(side='left')

        tools = self.setting_panel(3, 'App & diagnostics', 'Your settings stay in your Windows user profile, separate from the EXE.')
        row = ctk.CTkFrame(tools, fg_color='transparent')
        row.pack(fill='x', padx=20, pady=(0, 16))
        button(row, 'Create desktop shortcut', self.make_shortcut, width=180).pack(side='left', padx=(0, 10))
        button(row, 'Open data folder', lambda: os.startfile(str(self.store.directory)), width=135).pack(side='left')
        license_dir = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1])) / 'licenses'
        button(row, 'License notices', lambda: os.startfile(str(license_dir)), width=125).pack(side='left', padx=(10, 0))
        label(tools, f'Volumaty {__version__}  /  Built with Python\nLogs: volumaty.log  /  Settings: settings.json',
              size=11, color=MUTED, anchor='w', justify='left').pack(fill='x', padx=20, pady=(0, 17))

    def refresh_startup(self):
        state = self.startup.status()
        self.startup_switch.select() if state.registered else self.startup_switch.deselect()
        if state.blocked:
            text = 'Registered, but disabled by Windows. Enable Volumaty in Task Manager > Startup apps.'
        elif state.registered and not state.matches:
            text = 'The registered path is outdated. Update it to this version of Volumaty.'
        elif state.matches:
            text = 'Ready. Volumaty will start in the tray at your next Windows sign-in.'
        else:
            text = 'Off. Enable to start automatically at sign-in.'
        self.startup_status_label.configure(text=text, wraplength=650)
        self.repair_button.pack_forget()
        if state.registered and not state.matches:
            self.repair_button.pack(anchor='w', padx=20, pady=(0, 16))

    def toggle_startup(self):
        try:
            self.startup.set_enabled(bool(self.startup_switch.get()))
            self.refresh_startup()
            self.notify('Windows startup setting updated.')
        except (OSError, ValueError) as exc:
            log.exception('Startup registration failed')
            self.notify(f'Could not update startup: {exc}', error=True)
            self.refresh_startup()

    def repair_startup(self):
        try:
            self.startup.set_enabled(True)
            self.refresh_startup()
            self.notify('Startup now points to this copy of Volumaty.')
        except (OSError, ValueError) as exc:
            self.notify(str(exc), error=True)

    def change_step(self, value):
        self.settings.step = round(value)
        self.step_label.configure(text=f'{self.settings.step}%')
        self.changed()

    def change_close(self):
        self.settings.close_to_tray = bool(self.close_switch.get())
        self.changed()

    def make_shortcut(self):
        if self.isolated:
            self.notify('Desktop shortcuts are disabled in the preview profile.')
            return
        try:
            path = desktop_path() / 'Volumaty.lnk'
            if path.exists():
                self.notify('A Volumaty desktop shortcut already exists. Remove it first to replace it.')
                return
            create_shortcut(path)
            self.notify('Desktop shortcut created.')
        except Exception as exc:
            log.exception('Shortcut creation failed')
            self.notify(f'Could not create shortcut: {exc}', error=True)

    def export_settings(self):
        self.cancel_capture()
        destination = filedialog.asksaveasfilename(parent=self, title='Export Volumaty settings',
                                                  initialfile='Volumaty-settings.json',
                                                  defaultextension='.json', filetypes=[('JSON settings', '*.json')])
        if not destination:
            return
        try:
            self.store.export_settings(self.settings, destination)
            self.notify('Settings exported successfully.')
        except (OSError, ValueError) as exc:
            log.exception('Settings export failed')
            self.notify(f'Could not export settings: {exc}', error=True)

    def import_settings(self):
        self.cancel_capture()
        source = filedialog.askopenfilename(parent=self, title='Import Volumaty settings',
                                            filetypes=[('JSON settings', '*.json')])
        if not source:
            return
        if not messagebox.askyesno('Import settings',
                                  'Replace your app cards and shortcuts with this file?\nA backup of your saved settings will be kept.',
                                  parent=self):
            return
        try:
            # Flush pending edits before backing up; cancel their scheduled save.
            if self.save_job:
                self.after_cancel(self.save_job)
                self.save_job = None
            if not self.save_settings():
                return
            imported = self.store.import_settings(source)
            self.settings = imported
            self.keyboard.configure(imported)
            self.update_counts()
            self.show_settings()
            self.notify('Settings imported. Your previous settings were backed up in the data folder.')
        except (OSError, ValueError) as exc:
            log.exception('Settings import failed')
            self.notify(f'Could not import settings: {exc}', error=True)

    def start_tray(self):
        import pystray
        try:
            self.tray = pystray.Icon('Volumaty', tray_image(), 'Volumaty', pystray.Menu(
                pystray.MenuItem('Open Volumaty', lambda *_: self.messages.put(('show', None)), default=True),
                pystray.MenuItem('Pause / resume controls', lambda *_: self.messages.put(('pause', None))),
                pystray.MenuItem('Quit Volumaty', lambda *_: self.messages.put(('quit', None)))))
            self.tray.run_detached()
        except Exception:
            log.exception('System tray unavailable')
            self.tray = None
            self.notify('System tray unavailable. The window will stay open.', error=True)

    def close_window(self):
        self.cancel_capture()
        if not self.save_settings():
            return
        if self.settings.close_to_tray and self.tray:
            self.withdraw()
        else:
            self.quit_app()

    def show_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def quit_app(self):
        if self.quitting:
            return
        if not self.save_settings():
            self.show_window()
            return
        self.quitting = True
        if self.save_job:
            self.after_cancel(self.save_job)
        self.keyboard.stop()
        self.audio.stop()
        if self.tray:
            self.tray.stop()
        self.destroy()

    def pump(self):
        if self.quitting:
            return
        self.keyboard.check_timeout()
        if self.instance.requested_show():
            self.show_window()
        for _ in range(200):
            try:
                kind, payload = self.messages.get_nowait()
            except Empty:
                break
            if kind == 'audio':
                self.snapshot = payload
                names = tuple(sorted(s['name'] for s in payload.values()))
                changed_names = names != self._last_names
                self._last_names = names
                for card in self.cards:
                    if changed_names:
                        card.picker.configure(values=self.app_names(card.slot))
                    card.update_audio(payload.get(card.slot.app.lower()))
            elif kind == 'capture':
                self.finish_capture(payload)
            elif kind == 'keyboard':
                self.keyboard_ready = payload
                self.hook_label.configure(text='Controls active' if payload else 'Hook unavailable',
                                          text_color=ACCENT if payload else DANGER)
            elif kind == 'error':
                self.notify(payload, error=True)
            elif kind == 'show':
                self.show_window()
            elif kind == 'pause':
                self.toggle_pause()
            elif kind == 'quit':
                self.quit_app()
                if self.quitting:
                    return
        self.after(50, self.pump)

    def report_error(self, exc_type, value, traceback):
        log.error('UI callback failed', exc_info=(exc_type, value, traceback))
        self.notify('An operation failed. Details are in volumaty.log.', error=True)
