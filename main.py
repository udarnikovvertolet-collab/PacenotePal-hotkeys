import os
import threading
import time
import tkinter as tk
import tkinter.messagebox as mb
from tkinter import ttk

import keyboard
from pycaw import pycaw
import yaml

import util
from acrally import ACRally
from editor import Editor


# Maps Tkinter keysym names to the key names expected by the `keyboard` library.
TK_TO_KEYBOARD = {
    "Return": "enter",
    "BackSpace": "backspace",
    "Tab": "tab",
    "Escape": "esc",
    "Shift_L": "shift",
    "Shift_R": "shift",
    "Control_L": "ctrl",
    "Control_R": "ctrl",
    "Alt_L": "alt",
    "Alt_R": "alt",
    "space": "space",
    "Left": "left",
    "Right": "right",
    "Up": "up",
    "Down": "down",
    "Delete": "delete",
    "Insert": "insert",
    "Home": "home",
    "End": "end",
    "Prior": "page up",
    "Next": "page down",
}


def tk_to_keyboard(event):
    """Converts a Tkinter key event into the key name format expected by the `keyboard` library."""
    if event.keysym in TK_TO_KEYBOARD:
        return TK_TO_KEYBOARD[event.keysym]

    if event.char and event.char.isprintable():
        return event.char.lower()

    if event.keysym.startswith("F") and event.keysym[1:].isdigit():
        return event.keysym.lower()

    return event.keysym.lower()


def bind_key_capture(entry, string_var, allow_clear=False):
    """
    Binds an Entry widget so that pressing any key fills it in with the
    corresponding `keyboard`-library key name, instead of letting the user
    type freely.

    If `allow_clear` is True, pressing Backspace or Delete empties the field
    instead of capturing them as a literal key name. This is meant for
    optional hotkey fields, where an empty value means "no hotkey, this
    feature is disabled" (as opposed to the required "Start button" field,
    where an empty value would not make sense).
    """
    def on_key_release(event):
        key_name = tk_to_keyboard(event)
        if allow_clear and key_name in ("backspace", "delete"):
            string_var.set("")
        else:
            string_var.set(key_name)
    entry.bind("<KeyRelease>", on_key_release)


class Main:
    root = None
    stages = None
    voices = None
    call_earliness = None
    acrally = None
    btn_start = None
    btn_stop = None
    config = None
    hotkey_start_handle = None
    hotkey_stop_handle = None


    def on_button_start(self):
        print(self.stages.get())
        self.acrally = ACRally(
            str(self.stages.get()),
            self.config.get("voice", "English"),
            float(self.config.get("call_distance", 3.0)),
            int(self.config.get("calls_ahead", 4)),
            float(self.config.get("call_speed_multiplier", 1.0)),
            self.config.get("start_button", "space"),
            self.config.get("handbrake", None)
        )
        self.acrally.start()
        self.btn_start["state"] = "disabled"
        self.btn_stop["state"] = "normal"


    def on_button_exit(self):
        if self.acrally:
            self.acrally.exit()
        self.btn_start["state"] = "normal"
        self.btn_stop["state"] = "disabled"

    def trigger_start_hotkey(self):
        """
        Invoked on the main thread (via root.after) when the global Start
        hotkey is pressed. Mirrors a manual click on the Start button, but
        only acts if the app is currently stopped, i.e. the Start button is
        enabled - exactly like a real click would (a disabled button can't
        be clicked, so a disabled state must also block the hotkey).
        """
        if str(self.btn_start["state"]) == "normal":
            self.on_button_start()

    def trigger_stop_hotkey(self):
        """
        Invoked on the main thread (via root.after) when the global Stop
        hotkey is pressed. Mirrors a manual click on the Stop button, but
        only acts if the app is currently running, i.e. the Stop button is
        enabled - same reasoning as trigger_start_hotkey above.
        """
        if str(self.btn_stop["state"]) == "normal":
            self.on_button_exit()

    def register_hotkeys(self):
        """
        (Re-)registers the global Start/Stop hotkeys based on the current
        contents of self.config. Safe to call repeatedly: any hotkey that
        was registered by a previous call is removed first, so this same
        method works both at startup and right after the user changes a
        hotkey in Settings and clicks Save.

        An empty hotkey string means "disabled" - no hook is registered for
        that action in that case.
        """
        if self.hotkey_start_handle is not None:
            try:
                keyboard.remove_hotkey(self.hotkey_start_handle)
            except KeyError:
                pass
            self.hotkey_start_handle = None

        if self.hotkey_stop_handle is not None:
            try:
                keyboard.remove_hotkey(self.hotkey_stop_handle)
            except KeyError:
                pass
            self.hotkey_stop_handle = None

        hotkey_start = self.config.get("hotkey_start", "").strip()
        hotkey_stop = self.config.get("hotkey_stop", "").strip()

        if hotkey_start:
            try:
                self.hotkey_start_handle = keyboard.add_hotkey(
                    hotkey_start, lambda: self.root.after(0, self.trigger_start_hotkey)
                )
            except Exception as e:
                mb.showerror(
                    "Invalid hotkey",
                    f"Could not register the Start hotkey \"{hotkey_start}\":\n{e}\n\n"
                    "This hotkey has been disabled. Please pick a different key in Settings."
                )

        if hotkey_stop:
            try:
                self.hotkey_stop_handle = keyboard.add_hotkey(
                    hotkey_stop, lambda: self.root.after(0, self.trigger_stop_hotkey)
                )
            except Exception as e:
                mb.showerror(
                    "Invalid hotkey",
                    f"Could not register the Stop hotkey \"{hotkey_stop}\":\n{e}\n\n"
                    "This hotkey has been disabled. Please pick a different key in Settings."
                )

    def on_button_distance(self):
        distance_window = tk.Toplevel(self.root)
        distance_window.title("Odometer")
        distance_window.iconbitmap(util.resource_path("icon.ico"))
        distance_window.geometry("200x100")
        distance_window.attributes("-topmost", True)
        distance_var = tk.StringVar()
        distance_var.set("----")
        distance_label = ttk.Label(distance_window, textvariable=distance_var, font=("sans-serif", 40))
        distance_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        stop = False

        def retrieve_distance():
            nonlocal stop
            while not stop:
                if self.acrally:
                    if distance := self.acrally.get_distance():
                        distance_var.set(str(int(distance)))
                    else:
                        distance_var.set("----")
                time.sleep(0.05)

        def on_close():
            nonlocal stop
            stop = True
            distance_window.destroy()

        worker = threading.Thread(target=retrieve_distance, daemon=True)
        worker.start()
        distance_window.protocol("WM_DELETE_WINDOW", on_close)

    def on_button_pacenotes(self):
        editor = Editor()
        editor.main()

    def on_button_settings(self):
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Settings")
        settings_window.iconbitmap(util.resource_path("icon.ico"))
        settings_window.geometry("280x620")

        settings_frame = ttk.Frame(settings_window)
        settings_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(settings_frame, text="Voice").grid(column=0, row=0, padx=5, pady=5)
        voice_var = tk.StringVar(value=self.config.get("voice", "English"))
        voice_combo = ttk.Combobox(settings_frame, values=[x.strip() for x in os.listdir("voices")], textvariable=voice_var)
        voice_combo.grid(column=1, row=0, padx=5, pady=5)

        ttk.Label(settings_frame, text="Call distance").grid(column=0, row=1, padx=5, pady=5)
        call_distance_var = tk.DoubleVar(value=self.config.get("call_distance", 3.0))
        call_distance_spinbox = ttk.Spinbox(settings_frame, textvariable=call_distance_var, from_=0.1, to=15.0, increment=0.1)
        call_distance_spinbox.grid(column=1, row=1, padx=5, pady=5)

        ttk.Label(settings_frame, text="Call distance in seconds before the corner:\n"
                                       "2.0 means two seconds before the corner"
                  ).grid(column=0, columnspan=2, row=2, sticky="W")

        ttk.Label(settings_frame, text="Calls ahead").grid(column=0, row=3, padx=5, pady=5)
        calls_ahead_var = tk.IntVar(value=self.config.get("calls_ahead", 4))
        calls_ahead_spinbox = ttk.Spinbox(settings_frame, textvariable=calls_ahead_var, from_=1, to=10, increment=1)
        calls_ahead_spinbox.grid(column=1, row=3, padx=5, pady=5)

        ttk.Label(settings_frame, text="The maximum number of notes you want to\n"
                                       "hear coming up that you have not passed yet."
                  ).grid(column=0, columnspan=2, row=4, sticky="W")

        ttk.Label(settings_frame, text="Speed multiplier").grid(column=0, row=5, padx=5, pady=5)
        call_speed_multiplier_var = tk.DoubleVar(value=self.config.get("call_speed_multiplier", 1.0))
        call_speed_multiplier_spinbox = ttk.Spinbox(settings_frame, textvariable=call_speed_multiplier_var, from_=0.0, to=2.0, increment=0.01)
        call_speed_multiplier_spinbox.grid(column=1, row=5, padx=5, pady=5)

        ttk.Label(settings_frame, text="The multiplier for how much earlier the call\n"
                                       "is made with higher speeds.\n\n"
                                       "1.0 is linear, 2.0 is quadratic, 0.5 is radical,\n"
                                       "0.0 disables the speed influence entirely\n"
                                       "making \"Call distance\" the distance in metres"
                  ).grid(column=0, columnspan=2, row=6, sticky="W")

        ttk.Label(settings_frame, text="Start button").grid(column=0, row=7, padx=5, pady=5)
        start_var = tk.StringVar(value=self.config.get("start_button", "space"))
        start_entry = ttk.Entry(settings_frame, textvariable=start_var)
        start_entry.grid(column=1, row=7, padx=5, pady=5)
        bind_key_capture(start_entry, start_var)

        ttk.Label(settings_frame, text="Button to press at the start of the stage.\n"
                                       "See the README to use your handbrake instead."
                  ).grid(column=0, columnspan=2, row=8, sticky="W")

        ttk.Label(settings_frame, text="Hotkey: Start").grid(column=0, row=9, padx=5, pady=5)
        hotkey_start_var = tk.StringVar(value=self.config.get("hotkey_start", ""))
        hotkey_start_entry = ttk.Entry(settings_frame, textvariable=hotkey_start_var)
        hotkey_start_entry.grid(column=1, row=9, padx=5, pady=5)
        bind_key_capture(hotkey_start_entry, hotkey_start_var, allow_clear=True)

        ttk.Label(settings_frame, text="Hotkey: Stop").grid(column=0, row=10, padx=5, pady=5)
        hotkey_stop_var = tk.StringVar(value=self.config.get("hotkey_stop", ""))
        hotkey_stop_entry = ttk.Entry(settings_frame, textvariable=hotkey_stop_var)
        hotkey_stop_entry.grid(column=1, row=10, padx=5, pady=5)
        bind_key_capture(hotkey_stop_entry, hotkey_stop_var, allow_clear=True)

        ttk.Label(settings_frame, text="Global hotkeys for the Start/Stop buttons -\n"
                                       "they work even while Assetto Corsa has focus,\n"
                                       "so you don't need to alt-tab. Leave a field\n"
                                       "empty to disable it; press Backspace/Delete\n"
                                       "in the field to clear it. Start and Stop\n"
                                       "must use two different keys."
                  ).grid(column=0, columnspan=2, row=11, sticky="W")

        def get_volume():
            current_pid = os.getpid()
            sessions = pycaw.AudioUtilities.GetAllSessions()

            for session in sessions:
                if session.Process and session.Process.pid == current_pid:
                    audio_volume = session._ctl.QueryInterface(pycaw.ISimpleAudioVolume)
                    return audio_volume.GetMasterVolume()
            return 1.0

        def set_volume(volume):
            volume = volume_var.get() / 100
            volume = max(0.0, min(1.0, volume))  # clamp

            current_pid = os.getpid()
            sessions = pycaw.AudioUtilities.GetAllSessions()

            for session in sessions:
                if session.Process and session.Process.pid == current_pid:
                    audio_volume = session._ctl.QueryInterface(pycaw.ISimpleAudioVolume)
                    audio_volume.SetMasterVolume(volume, None)
                    return True
            return False

        ttk.Label(settings_frame, text="Volume").grid(column=0, row=12, padx=5, pady=5)
        volume_var = tk.DoubleVar(value=get_volume() * 100)
        volume_scale = ttk.Scale(settings_frame, variable=volume_var, from_=0, to=100, command=set_volume)
        volume_scale.bind("<ButtonRelease>", lambda e: util.play_beep())
        volume_scale.grid(column=1, row=12, padx=5, pady=5)

        def save():
            new_hotkey_start = hotkey_start_var.get().strip()
            new_hotkey_stop = hotkey_stop_var.get().strip()

            if new_hotkey_start and new_hotkey_start == new_hotkey_stop:
                mb.showerror(
                    "Conflicting hotkeys",
                    "The Start and Stop hotkeys cannot be the same key.\n"
                    "Please choose two different keys."
                )
                return

            self.config["voice"] = voice_var.get()
            self.config["start_button"] = start_var.get()
            self.config["call_distance"] = call_distance_var.get()
            self.config["calls_ahead"] = calls_ahead_var.get()
            self.config["call_speed_multiplier"] = call_speed_multiplier_var.get()
            self.config["hotkey_start"] = new_hotkey_start
            self.config["hotkey_stop"] = new_hotkey_stop
            yaml.dump(self.config, open("config.yml", "w", encoding="utf-8"))
            self.register_hotkeys()
            settings_window.withdraw()

        save_btn = ttk.Button(settings_frame, text="Save", command=save)
        save_btn.grid(column=0, columnspan=2, row=13, padx=5, pady=5)

    def __init__(self):
        self.config = yaml.safe_load(open("config.yml", encoding="utf-8"))

        root = tk.Tk()
        root.title("AC Rally Pacenote Pal")
        root.iconbitmap(util.resource_path("icon.ico"))
        root.geometry("340x230")
        self.root = root

        stages = os.listdir("pacenotes")
        stages = [file.replace(".yml", "") for file in stages]

        ttk.Label(root, text="Select a stage:").pack(pady=(20, 5))
        self.stages = ttk.Combobox(root, values=stages, width=50)
        self.stages.pack(pady=5, padx=15, fill="x")

        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=10)

        self.btn_start = ttk.Button(btn_frame, text="Start", command=self.on_button_start)
        self.btn_start.pack(side=tk.LEFT, padx=10)

        self.btn_stop = ttk.Button(btn_frame, text="Stop", command=self.on_button_exit, state="disabled")
        self.btn_stop.pack(side=tk.LEFT, padx=10)

        btn_distance = ttk.Button(btn_frame, text="Odometer", command=self.on_button_distance)
        btn_distance.pack(side=tk.LEFT, padx=10)

        ttk.Label(root, text=f"Click start and press {self.config.get("start_button", "space")} when the countdown starts!").pack(pady=(20, 5))

        btn_frame2 = tk.Frame(root)
        btn_frame2.pack(pady=10)

        btn_editor = ttk.Button(btn_frame2, text="Pacenote Editor", command=self.on_button_pacenotes)
        btn_editor.pack(side=tk.LEFT, padx=10)

        btn_settings = ttk.Button(btn_frame2, text="Settings", command=self.on_button_settings)
        btn_settings.pack(side=tk.LEFT, padx=10)

        # Play nothing to start audio session
        threading.Thread(target=util.initialise_audio, daemon=True).start()

        self.register_hotkeys()

        root.mainloop()

if __name__ == '__main__':
    app = Main()
