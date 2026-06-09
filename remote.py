import customtkinter as ctk
from tkinter import filedialog
import serial
import time
import datetime
import sys


import lang #CZ/EN dictionary
import leica #commands

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# hardware config
SERIAL_PORT = '/dev/serial0'
BAUD_RATE = 9600          
SET_PIN = 18

# temperature offset correction
temp_offset = -3


POSIT_STEP   = 5      # left/right step size [gon]
SEARCH_RANGE = 10     # search range [gon]



# atmos to PPM corrections 
ATMOS_C0    = 286.34
ATMOS_C1    = 0.29525
ATMOS_ALPHA = 1 / 273.15
def atmos_ppm(t, p):
    return ATMOS_C0 - (ATMOS_C1 * p) / (1 + ATMOS_ALPHA * t)

# inicialization
HAS_GPIO = False
try:
    import RPi.GPIO as GPIO
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(SET_PIN, GPIO.OUT)
    HAS_GPIO = True
except ImportError:
    print("GPIO error")


# HC-12 configuration
def configure_hc12():
    if not HAS_GPIO:
        print("GPIO error")
        return

    print("\nHC-12 config")
    GPIO.output(SET_PIN, GPIO.LOW)
    time.sleep(0.2)

    try:
        ser = serial.Serial(SERIAL_PORT, 9600, timeout=0.5)
        ser.reset_input_buffer()

        def send_at(cmd):
            ser.reset_input_buffer()
            ser.write(cmd.encode())
            time.sleep(0.2)
            ser.read(ser.in_waiting)  

        print("AT config") # AT commands config
        
        # set defoult values
        send_at("AT+C001")      # channel 1
        send_at("AT+P8")        # 20 dBm
        send_at("AT+FU3")       # Standard mode
        send_at("AT+B9600")     # Baud rate
        
        time.sleep(0.2)
        ser.close()
        
        print("config succes\n")

    except Exception as e:
        print(f"config error: {e}")

    GPIO.output(SET_PIN, GPIO.HIGH)
    time.sleep(0.3)



# start screen
class StartPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=("#ebebeb", "#37474f"))
        self.controller = controller
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkLabel(self, text="ONE MAN SYSTEM", font=("Roboto", 24, "bold"), text_color=("#1e1e1e", "#eceff1")).grid(row=0, column=0, pady=(40, 10))

        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.grid(row=1, column=0)

        ctk.CTkButton(self.btn_frame, text=controller.tr("new_job"), font=("Roboto", 18, "bold"),
                      width=250, height=80, fg_color=("#66bb6a", "#8acb9b"), text_color=("#001a0b", "#173d26"),
                      hover=False, command=self.create_project).pack(pady=15)

        ctk.CTkButton(self.btn_frame, text=controller.tr("select_job"), font=("Roboto", 18, "bold"),
                      width=250, height=80, fg_color=("#81d4fa", "#b8ecff"), text_color=("#002736", "#0a5270"),
                      hover=False, command=self.open_project).pack(pady=15)

        lang_frame = ctk.CTkFrame(self, fg_color="transparent")
        lang_frame.grid(row=2, column=0, pady=10)

        ctk.CTkButton(lang_frame, text="CZ", width=80, height=40, hover=False, font=("Roboto", 16, "bold"),
                      fg_color=("#66bb6a", "#8acb9b") if controller.lang == "CZ" else ("#b0bec5", "#546e7a"),
                      command=lambda: controller.change_language("CZ", return_to="start")).pack(side="left", padx=10)
        ctk.CTkButton(lang_frame, text="EN", width=80, height=40, hover=False, font=("Roboto", 16, "bold"),
                      fg_color=("#66bb6a", "#8acb9b") if controller.lang == "EN" else ("#b0bec5", "#546e7a"),
                      command=lambda: controller.change_language("EN", return_to="start")).pack(side="left", padx=10)

        ctk.CTkLabel(self, text="2026 - Martin Ludvík", font=("Roboto", 12), text_color=("#546e7a", "#90a4ae")).grid(row=3, column=0, pady=10)

    def create_project(self): # create project function
        default_name = f"job_{datetime.datetime.now().strftime('%Y%m%d')}"
        filename = filedialog.asksaveasfilename(initialfile=default_name, defaultextension=".txt",
                                                filetypes=[("Text file", "*.txt")])
        if filename: 
            with open(filename, 'w') as f:
                f.write(f"; Zakazka: {default_name}, Datum: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}\n")
                f.write("512\n360607101\n660205\n1\n3\n0\n0\n")
            self.controller.set_project(filename)
            self.controller.show_frame("dashboard")

    def open_project(self):  # open project function
        filename = filedialog.askopenfilename(filetypes=[("Text file", "*.txt")])
        if filename:
            self.controller.set_project(filename)
            self.controller.show_frame("dashboard")


# main dashboard
class DashboardPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=("#ebebeb", "#37474f"))
        self.controller = controller
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0); self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1); self.grid_rowconfigure(3, weight=0)

        self.job_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.job_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        self.job_frame.grid_columnconfigure((0, 1, 3, 4), weight=1)
        self.job_frame.grid_columnconfigure(2, weight=0)

        # station
        ctk.CTkLabel(self.job_frame, text=controller.tr("station"), font=("Roboto", 14, "bold")).grid(row=0, column=0, sticky="e")
        self.st_sub = ctk.CTkFrame(self.job_frame, fg_color="transparent")
        self.st_sub.grid(row=0, column=1, sticky="w")
        self.ent_station = ctk.CTkEntry(self.st_sub, width=70, justify="center")
        self.ent_station.insert(0, "5001")
        self.ent_station.pack(side="left", padx=2)
        self.ent_station.bind("<Button-1>", lambda e: self.controller.open_numpad(self.ent_station, controller.tr("station")))

        self.st_btns = ctk.CTkFrame(self.st_sub, fg_color="transparent")
        self.st_btns.pack(side="left")
        ctk.CTkButton(self.st_btns, text="▲", width=30, height=20, fg_color=("#66bb6a", "#8acb9b"), text_color="black", hover=False, command=self.inc_st).pack(pady=1)
        ctk.CTkButton(self.st_btns, text="▼", width=30, height=20, fg_color=("#66bb6a", "#8acb9b"), text_color="black", hover=False, command=self.dec_st).pack()

        # cface
        self.btn_center = ctk.CTkButton(self.job_frame, text="otočit polohu", width=50, height=40, font=("Arial", 16, "bold"),
                                        fg_color=("#81d4fa", "#b8ecff"), text_color=("#002736", "#0a5270"), hover=False,
                                        command=lambda: controller.send("CFACE"))
        self.btn_center.grid(row=0, column=2, rowspan=2, padx=10)

        # point
        ctk.CTkLabel(self.job_frame, text=controller.tr("point"), font=("Roboto", 14, "bold")).grid(row=0, column=3, sticky="e")
        self.pt_sub = ctk.CTkFrame(self.job_frame, fg_color="transparent")
        self.pt_sub.grid(row=0, column=4, sticky="w")
        self.ent_point = ctk.CTkEntry(self.pt_sub, width=70, justify="center")
        self.ent_point.insert(0, "1")
        self.ent_point.pack(side="left", padx=2)
        self.ent_point.bind("<Button-1>", lambda e: self.controller.open_numpad(self.ent_point, controller.tr("point")))

        self.pt_btns = ctk.CTkFrame(self.pt_sub, fg_color="transparent")
        self.pt_btns.pack(side="left")
        ctk.CTkButton(self.pt_btns, text="▲", width=30, height=20, fg_color=("#66bb6a", "#8acb9b"), text_color="black", hover=False, command=self.inc_pt).pack(pady=1)
        ctk.CTkButton(self.pt_btns, text="▼", width=30, height=20, fg_color=("#66bb6a", "#8acb9b"), text_color="black", hover=False, command=self.dec_pt).pack()

        # heights
        ctk.CTkLabel(self.job_frame, text=controller.tr("station_height"), font=("Roboto", 14, "bold")).grid(row=1, column=0, sticky="e")
        self.ent_hi = ctk.CTkEntry(self.job_frame, width=70, justify="center")
        self.ent_hi.grid(row=1, column=1, sticky="w", pady=5, padx=2)
        self.ent_hi.bind("<Button-1>", lambda e: self.controller.open_numpad(self.ent_hi, controller.tr("station_height")))

        ctk.CTkLabel(self.job_frame, text=controller.tr("point_height"), font=("Roboto", 14, "bold")).grid(row=1, column=3, sticky="e")
        self.ent_ht = ctk.CTkEntry(self.job_frame, width=70, justify="center")
        self.ent_ht.grid(row=1, column=4, sticky="w", pady=5, padx=2)
        self.ent_ht.bind("<Button-1>", lambda e: self.controller.open_numpad(self.ent_ht, controller.tr("point_height")))

        # data cards
        self.info_frame = ctk.CTkFrame(self, fg_color=("#ebebeb", "#37474f"))
        self.info_frame.grid(row=1, column=0, sticky="ew", padx=10)
        self.info_frame.grid_columnconfigure((0, 1, 2), weight=1, uniform="cards")

        self.lbl_hz_val = self.create_data_card(self.info_frame, 0, "Hz (Gon)", "---.----")
        self.lbl_v_val = self.create_data_card(self.info_frame, 1, "V (Gon)", "---.----")
        self.lbl_dist_val = self.create_data_card(self.info_frame, 2, "D (m)", "---.---")

        # terminal
        self.terminal_out = ctk.CTkTextbox(self, fg_color=("#cfd8dc", "#263238"), text_color=("#2e7d32", "#9ccc65"), font=("Consolas", 14))
        self.terminal_out.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        self.terminal_out.configure(state="disabled")

        # remote buttons
        self.controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.controls_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=10)
        self.controls_frame.grid_columnconfigure((0, 1, 2), weight=1)

       
        self.btn_left = ctk.CTkButton(self.controls_frame, text="< " + controller.tr("left"), height=50, font=("Roboto", 14, "bold"),
                                      fg_color=("#81d4fa", "#b8ecff"), text_color=("#002736", "#0a5270"), hover=False,
                                      command=lambda: self.controller.send("LEFT"))
        self.btn_left.grid(row=0, column=0, padx=3, pady=3, sticky="ew")

        self.btn_search = ctk.CTkButton(self.controls_frame, text=controller.tr("search"), height=50, font=("Roboto", 14, "bold"),
                                        fg_color=("#66bb6a", "#8acb9b"), text_color=("#001a0b", "#173d26"), hover=False,
                                        command=lambda: self.controller.send("SEARCH"))
        self.btn_search.grid(row=0, column=1, padx=3, pady=3, sticky="ew")

        self.btn_right = ctk.CTkButton(self.controls_frame, text=controller.tr("right") + " >", height=50, font=("Roboto", 14, "bold"),
                                       fg_color=("#81d4fa", "#b8ecff"), text_color=("#002736", "#0a5270"), hover=False,
                                       command=lambda: self.controller.send("RIGHT"))
        self.btn_right.grid(row=0, column=2, padx=3, pady=3, sticky="ew")

  
        color_egl = ("#66bb6a", "#8acb9b") if self.controller.egl_on else "#d9dddd"
        text_egl = ("#001a0b", "#173d26") if self.controller.egl_on else "#353535"
        self.btn_egl = ctk.CTkButton(self.controls_frame, text=f"EGL: {'ON' if self.controller.egl_on else 'OFF'}", height=50, font=("Roboto", 14, "bold"),
                                     fg_color=color_egl, text_color=text_egl, hover=False,
                                     command=self.controller.toggle_egl)
        self.btn_egl.grid(row=1, column=0, padx=3, pady=3, sticky="ew")

        self.btn_measure = ctk.CTkButton(self.controls_frame, text=controller.tr("measure"), height=50, font=("Roboto", 14, "bold"),
                                         fg_color=("#ef5350", "#fb6b68"), text_color=("#3e1006", "#6e1c0c"), hover=False,
                                         command=lambda: self.controller.send("MEASURE"))
        self.btn_measure.grid(row=1, column=1, padx=3, pady=3, sticky="ew")

        color_lock = ("#66bb6a", "#8acb9b") if self.controller.lock_on else "#d9dddd"
        text_lock = ("#001a0b", "#173d26") if self.controller.lock_on else "#353535"
        self.btn_lock = ctk.CTkButton(self.controls_frame, text=f"LOCK: {'ON' if self.controller.lock_on else 'OFF'}", height=50, font=("Roboto", 14, "bold"),
                                      fg_color=color_lock, text_color=text_lock, hover=False,
                                      command=self.controller.toggle_lock)
        self.btn_lock.grid(row=1, column=2, padx=3, pady=3, sticky="ew")

    def create_data_card(self, parent, col, title, initial_value):
        frame = ctk.CTkFrame(parent, fg_color=("#ffffff", "#cfd8dc"))
        frame.grid(row=0, column=col, padx=5, pady=5, sticky="nsew")
        ctk.CTkLabel(frame, text=title, text_color=("#1e1e1e", "#3b3b3b"), font=("Roboto", 11)).pack(pady=(5, 0))
        lbl = ctk.CTkLabel(frame, text=initial_value, font=("Roboto", 32, "bold"), text_color=("#000000", "#263238"), width=200)
        lbl.pack(pady=(2, 10))
        return lbl

    # ID incresement
    def inc_st(self):
        v = int(self.ent_station.get()); self.ent_station.delete(0, "end"); self.ent_station.insert(0, str(v + 1))
    def dec_st(self):
        v = int(self.ent_station.get()); self.ent_station.delete(0, "end"); self.ent_station.insert(0, str(v - 1))
    def inc_pt(self):
        v = int(self.ent_point.get()); self.ent_point.delete(0, "end"); self.ent_point.insert(0, str(v + 1))
    def dec_pt(self):
        v = int(self.ent_point.get()); self.ent_point.delete(0, "end"); self.ent_point.insert(0, str(v - 1))


# settings
class SettingsPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=("#ebebeb", "#37474f"))
        self.controller = controller
        self.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(self, text=controller.tr("settings"),
                     font=("Roboto", 24, "bold"),
                     text_color=("#1e1e1e", "#eceff1")).grid(row=0, column=0, columnspan=3, pady=(30, 20))

        ctk.CTkLabel(self, text=controller.tr("temperature"), font=("Roboto", 16)).grid(row=1, column=0, sticky="e", padx=10, pady=10)
        self.ent_temp = ctk.CTkEntry(self, width=120, font=("Roboto", 16), justify="center")
        self.ent_temp.insert(0, "")
        self.ent_temp.grid(row=1, column=1, sticky="w", pady=10)
        self.ent_temp.bind("<Button-1>", lambda e: self.controller.open_numpad(self.ent_temp, controller.tr("temperature")))

        ctk.CTkLabel(self, text=controller.tr("pressure"), font=("Roboto", 16)).grid(row=2, column=0, sticky="e", padx=10, pady=10)
        self.ent_pressure = ctk.CTkEntry(self, width=120, font=("Roboto", 16), justify="center")
        self.ent_pressure.insert(0, "")
        self.ent_pressure.grid(row=2, column=1, sticky="w", pady=10)
        self.ent_pressure.bind("<Button-1>", lambda e: self.controller.open_numpad(self.ent_pressure, controller.tr("pressure")))

        self.btn_read = ctk.CTkButton(self, text=controller.tr("read_sensor"),
                                      width=200, height=50,
                                      fg_color=("#81d4fa", "#b8ecff"), text_color=("#001a0b", "#173d26"), font=("Roboto", 14, "bold"),
                                      hover=False, command=controller.read_bme)
        self.btn_read.grid(row=1, column=2, rowspan=2, padx=0, sticky="w")

        ctk.CTkButton(self, text=controller.tr("send_station"),
                      font=("Roboto", 16, "bold"),
                      fg_color=("#66bb6a", "#8acb9b"), text_color=("#001a0b", "#173d26"),
                      width=200, height=50, hover=False,
                      command=lambda: self.controller.send("SET_ATMOS")).grid(row=3, column=0, columnspan=3, pady=40)

        ctk.CTkButton(self, text=controller.tr("back"),
                      fg_color=("#b0bec5", "#546e7a"), text_color=("black", "white"),
                      width=120, height=25, hover=False,
                      command=lambda: self.controller.show_frame("dashboard")).grid(row=4, column=0, columnspan=3, pady=10)

        lang_frame = ctk.CTkFrame(self, fg_color="transparent")
        lang_frame.grid(row=5, column=0, columnspan=3, pady=20)

        ctk.CTkButton(lang_frame, text="CZ", width=80, height=40, hover=False, font=("Roboto", 16, "bold"),
                      fg_color=("#66bb6a", "#8acb9b") if controller.lang == "CZ" else ("#b0bec5", "#546e7a"),
                      command=lambda: controller.change_language("CZ", return_to="settings")).pack(side="left", padx=10)

        ctk.CTkButton(lang_frame, text="EN", width=80, height=40, hover=False, font=("Roboto", 16, "bold"),
                      fg_color=("#66bb6a", "#8acb9b") if controller.lang == "EN" else ("#b0bec5", "#546e7a"),
                      command=lambda: controller.change_language("EN", return_to="settings")).pack(side="left", padx=10)


# main controller (window)
class OneManStationApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.lang = "CZ"
        self.title("Leica TCA 2003")
        self.geometry("800x480")

        self.attributes('-fullscreen', True)
        self.bind("<Escape>", lambda e: self.attributes("-fullscreen", False))

        self.ser = None
        self.project_file = None
        self.last_contact_time = 0
        self.last_heartbeat_time = 0
        self.last_saved_station = None
        self.last_saved_hi = None

        # GSI parser 
        self.parser = leica.GSIParser()
        self.meas_saved = False
        self.was_connected = False

        self.egl_on = False
        self.lock_on = False

        # Header
        self.header = ctk.CTkFrame(self, fg_color=("#cfd8dc", "#263238"))
        self.header.pack(side="top", fill="x", ipady=5)
        self.lbl_status = ctk.CTkLabel(self.header, text=self.tr("status_search"), text_color=("#e65100", "#e65100"), font=("Roboto", 14, "bold"))
        self.lbl_status.pack(side="left", padx=20)

        self.btn_menu = ctk.CTkButton(self.header, text=self.tr("menu"), font=("Roboto", 16, "bold"), fg_color=("#b0bec5", "#546e7a"), hover=False, command=self.open_menu_popup, width=120)
        self.btn_menu.pack(side="right", padx=10)

        # main window
        self.container = ctk.CTkFrame(self)
        self.container.pack(fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        self.create_frames()

        self.show_frame("start")
        self.connect_serial()
        self.after(100, self.serial_loop)

    def create_frames(self):
        for F, name in [(StartPage, "start"), (DashboardPage, "dashboard"), (SettingsPage, "settings")]:
            f = F(self.container, self)
            self.frames[name] = f
            f.grid(row=0, column=0, sticky="nsew")
    # languages
    def tr(self, key): 
        return lang.LANGUAGES[self.lang].get(key, key)
    # change language function
    def change_language(self, new_lang, return_to="settings"):
        if self.lang != new_lang:
            self.lang = new_lang
            for frame in self.frames.values():
                frame.destroy()
            self.frames.clear()
            self.create_frames()
            self.btn_menu.configure(text=self.tr("menu"))
            self.show_frame(return_to)

    # numpad
    def open_numpad(self, target_entry, title="Zadat hodnotu"):
        if hasattr(self, "numpad_overlay") and self.numpad_overlay:
            self.numpad_overlay.destroy()

        self.numpad_overlay = ctk.CTkFrame(self, fg_color=("#cfd8dc", "#263238"), border_width=2, border_color=("#b0bec5", "#546e7a"))
        self.numpad_overlay.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.40, relheight=0.85)

        self.numpad_target = target_entry
        self.numpad_value = target_entry.get()

        ctk.CTkLabel(self.numpad_overlay, text=title, font=("Roboto", 16, "bold"), text_color=("#546e7a", "#90a4ae")).pack(pady=(10, 5))

        self.lbl_numpad_display = ctk.CTkLabel(self.numpad_overlay, text=self.numpad_value, font=("Roboto", 32, "bold"),
                                               fg_color=("#ebebeb", "#37474f"), text_color=("black", "white"), width=250, height=50)
        self.lbl_numpad_display.pack(pady=(0, 15))

        kp_frame = ctk.CTkFrame(self.numpad_overlay, fg_color="transparent")
        kp_frame.pack(expand=True, fill="both", padx=20, pady=5)

        keys = [
            ('7', 0, 0), ('8', 0, 1), ('9', 0, 2),
            ('4', 1, 0), ('5', 1, 1), ('6', 1, 2),
            ('1', 2, 0), ('2', 2, 1), ('3', 2, 2),
            ('.', 3, 0), ('0', 3, 1), ('DEL', 3, 2)
        ]

        for key, r, c in keys:
            btn_color = "#fb6b68" if key == 'DEL' else ("#b0bec5", "#546e7a")
            btn = ctk.CTkButton(kp_frame, text=key, font=("Roboto", 24, "bold"), height=45, hover=False,
                                fg_color=btn_color, command=lambda k=key: self.numpad_press(k))
            btn.grid(row=r, column=c, padx=5, pady=5, sticky="ew")
            kp_frame.grid_columnconfigure(c, weight=1)

        ctk.CTkButton(self.numpad_overlay, text=self.tr("confirm"), fg_color=("#66bb6a", "#8acb9b"), text_color=("#001a0b", "#173d26"), hover=False,
                      height=50, font=("Roboto", 20, "bold"), command=self.confirm_numpad).pack(fill="x", padx=25, pady=(5, 15))

    def numpad_press(self, key):
        if key == 'DEL':
            self.numpad_value = self.numpad_value[:-1]
        else:
            self.numpad_value += key
        self.lbl_numpad_display.configure(text=self.numpad_value)

    def confirm_numpad(self):
        self.numpad_target.delete(0, "end")
        self.numpad_target.insert(0, self.numpad_value)
        self.numpad_overlay.destroy()
        self.numpad_overlay = None

    # menu popup
    def open_menu_popup(self):
        self.menu_overlay = ctk.CTkFrame(self, fg_color=("#cfd8dc", "#263238"), border_width=2, border_color=("#b0bec5", "#546e7a"))
        self.menu_overlay.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.6, relheight=0.7)
        self.menu_overlay.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.menu_overlay, text=self.tr("menu_title"), font=("Roboto", 18, "bold"), text_color=("#1e1e1e", "#eceff1")).pack(pady=(20, 20))

        btn_style = {"height": 45, "font": ("Roboto", 16, "bold"), "hover": False, "corner_radius": 8}
        ctk.CTkButton(self.menu_overlay, text=self.tr("menu_settings"), fg_color=("#b0bec5", "#546e7a"), command=lambda: self.handle_menu_action("settings"), **btn_style).pack(fill="x", padx=40, pady=10)
        ctk.CTkButton(self.menu_overlay, text=self.tr("menu_jobs"), fg_color=("#b0bec5", "#546e7a"), command=lambda: self.handle_menu_action("start"), **btn_style).pack(fill="x", padx=40, pady=10)
        ctk.CTkButton(self.menu_overlay, text=self.tr("menu_back"), fg_color=("#b0bec5", "#546e7a"), command=self.close_menu_popup, **btn_style).pack(fill="x", padx=40, pady=10)
        ctk.CTkButton(self.menu_overlay, text=self.tr("menu_quit"), fg_color=("#ef5350", "#fb6b68"), command=self.quit_app, **btn_style).pack(fill="x", padx=40, pady=20)

    def close_menu_popup(self):
        if hasattr(self, "menu_overlay") and self.menu_overlay:
            self.menu_overlay.destroy()
            self.menu_overlay = None

    def handle_menu_action(self, page_name):
        self.show_frame(page_name)
        self.close_menu_popup()

    def show_frame(self, name):
        self.frames[name].tkraise()
        if name == "start":
            self.btn_menu.pack_forget()
        else:
            self.btn_menu.pack(side="right", padx=10)

    # serail com
    def connect_serial(self):
        try:
            if self.ser:
                self.ser.close()
            self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
        except:
            self.ser = None

    def serial_loop(self):
        if self.ser and self.ser.is_open:
            try:
                while self.ser.in_waiting > 0:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if not line:
                        continue
                    self.last_contact_time = time.time()
                    if "PONG" in line:      # connection status 
                        continue
                    self.log_to_terminal(line, "RX")
                    self.handle_line(line)
            except:
                pass

            if time.time() - self.last_heartbeat_time > 5.0:
                self.send_direct("PING\n")     
                self.last_heartbeat_time = time.time()

        diff = time.time() - self.last_contact_time
        if self.ser is None or not self.ser.is_open:
            self.lbl_status.configure(text=self.tr("status_disconnected"), text_color="#fb6b68")
            self.was_connected = False
        elif diff < 6.5:
            self.lbl_status.configure(text=self.tr("status_ok"), text_color=("#66bb6a", "#8acb9b"))
            if not self.was_connected:          # success conection
                self.was_connected = True
                self.init_station()
        else:
            self.lbl_status.configure(text=self.tr("status_search"), text_color=("#e65100", "#e65100"))
            self.was_connected = False

        self.after(100, self.serial_loop)

    def init_station(self): # station initialization
        for cmd in (leica.set_terminator_crlf(),
                    leica.password(),
                    leica.set_angle_unit_gon(),
                    leica.set_dist_unit_meter(),
                    leica.set_format_gsi8()):
            self.log_to_terminal(cmd.strip(), "TX")
            self.send_direct(cmd)
            time.sleep(0.05)
        self.log_to_terminal("Stanice inicializována", "SYS")

    def send(self, act):
        cmds = {
            "MEASURE": leica.measure(("21", "22", "32")),    # Hz, V, VD 
            "LEFT":    leica.posit_rel(-POSIT_STEP, 0),      # turn left
            "RIGHT":   leica.posit_rel(POSIT_STEP, 0),       # turn right
            "SEARCH":  leica.posit_search(SEARCH_RANGE, SEARCH_RANGE),
            "CFACE":   leica.change_face(),                  # change face dir
        }

        if act == "MEASURE":
            self.parser.reset()
            self.meas_saved = False

        # set atmos function
        if act == "SET_ATMOS":
            s = self.frames["settings"]
            try:
                t = float(s.ent_temp.get())
                p = float(s.ent_pressure.get())
            except ValueError:
                self.log_to_terminal("Atmos error", "ERR")
                return
            ppm = atmos_ppm(t, p)
            cmd = leica.put_ppm(ppm)       # ppm function
            self.log_to_terminal(f"PPM={ppm:.1f} -> {cmd.strip()}", "TX")
            self.send_direct(cmd)
            return

        cmd = cmds.get(act, "")
        if cmd:
            self.log_to_terminal(cmd.strip(), "TX")
            self.send_direct(cmd)

    def send_direct(self, cmd):
        if self.ser and self.ser.is_open:
            for char in cmd:
                self.ser.write(char.encode('ascii'))
                time.sleep(0.015)

    def handle_line(self, data):
        # temp values
        if data.startswith("TEMP:"): 
            self.handle_bme(data)
            return
        # other values
        ev = self.parser.feed_line(data)
        if ev.get("error"):
            self.log_to_terminal(ev["error"], "ERR")
        elif ev.get("ack"):
            pass                          # '?' už je vypsané jako RX
        elif ev.get("words"):
            self.update_measurement(self.parser.meas)

    # temp parser
    def handle_bme(self, data):
        raw_data = data.replace("TEMP:", "").strip()
        values = raw_data.split(",")
        if len(values) == 2:
            teplota = float(values[0]) + temp_offset
            try:
                tlak_hpa = float(values[1]) / 100.0
                tlak_str = f"{tlak_hpa:.2f}"
            except ValueError:
                tlak_str = values[1]

            s = self.frames["settings"]
            s.ent_temp.delete(0, "end")
            s.ent_temp.insert(0, f"{teplota:.1f}")
            s.ent_pressure.delete(0, "end")
            s.ent_pressure.insert(0, tlak_str)
            self.log_to_terminal(f"{teplota:.1f}°C, {tlak_str} hPa", "BME")

    # dashboard update
    def update_measurement(self, meas):
        d = self.frames["dashboard"]

        if "21" in meas and isinstance(meas["21"], float):
            d.lbl_hz_val.configure(text=f"{meas['21']:.4f}")
        if "22" in meas and isinstance(meas["22"], float):
            d.lbl_v_val.configure(text=f"{meas['22']:.4f}")

        dist, typ = None, None
        if "32" in meas:   dist, typ = meas["32"], "VD [m]"   # vodorovná
        elif "31" in meas: dist, typ = meas["31"], "SD [m]"   # šikmá
        elif "33" in meas: dist, typ = meas["33"], "dH [m]"   # převýšení

        if isinstance(dist, float):
            d.lbl_dist_val.configure(text=f"{dist:.3f}")
            d.lbl_dist_val.master.winfo_children()[0].configure(text=typ)
            if (not self.meas_saved
                    and isinstance(meas.get("21"), float)
                    and isinstance(meas.get("22"), float)):
                self.save_to_file(f"{meas['21']:.4f}", f"{meas['22']:.4f}", f"{dist:.3f}")
                self.meas_saved = True

    # select project
    def set_project(self, filename):
        self.project_file = filename

    # save measurement to file
    def save_to_file(self, hz, v, dist):
        if self.project_file:
            d = self.frames["dashboard"]
            pt = d.ent_point.get()
            st = d.ent_station.get()

            vh = d.ent_ht.get(); vh = vh if vh.strip() else "0.000"
            hi = d.ent_hi.get(); hi = hi if hi.strip() else "0.000"

            if self.last_saved_station != st or self.last_saved_hi != hi:
                self.save_station()

            line = f"{pt} {dist} {vh} {hz} {v}\n"
            with open(self.project_file, "a") as f:
                f.write(line)

            d.inc_pt()

    # save station values to file
    def save_station(self):
        if self.project_file:
            d = self.frames["dashboard"]
            st = d.ent_station.get()
            hi = d.ent_hi.get(); hi = hi if hi.strip() else "0.000"

            line = f"1 {st} {hi}\n"
            with open(self.project_file, "a") as f:
                f.write(line)

            self.last_saved_station = st
            self.last_saved_hi = hi

    # toggle EGL
    def toggle_egl(self):
        self.egl_on = not self.egl_on
        self.send_direct(leica.set_egl(self.egl_on))   # SET/35 (str. 31)
        color_bg = ("#66bb6a", "#8acb9b") if self.egl_on else "#d9dddd"
        color_txt = ("#001a0b", "#173d26") if self.egl_on else "#353535"
        self.frames["dashboard"].btn_egl.configure(text=f"EGL: {'ON' if self.egl_on else 'OFF'}", fg_color=color_bg, text_color=color_txt)

    # toggle ATR
    def toggle_lock(self):
        self.lock_on = not self.lock_on

        self.send_direct(f"%R1Q,9037:{'1' if self.lock_on else '0'}\r\n")
        color_bg = ("#66bb6a", "#8acb9b") if self.lock_on else "#d9dddd"
        color_txt = ("#001a0b", "#173d26") if self.lock_on else "#353535"
        self.frames["dashboard"].btn_lock.configure(text=f"LOCK: {'ON' if self.lock_on else 'OFF'}", fg_color=color_bg, text_color=color_txt)

    # print to terminal
    def log_to_terminal(self, txt, pref="SYS"):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.frames["dashboard"].terminal_out.configure(state="normal")
        self.frames["dashboard"].terminal_out.insert("end", f"[{timestamp}] [{pref}] {txt}\n")
        self.frames["dashboard"].terminal_out.configure(state="disabled")
        self.frames["dashboard"].terminal_out.see("end")

    # read sensor data command
    def read_bme(self):
        self.send_direct("TEMP\n")
        self.log_to_terminal("Měření teploty a tlaku", "SYS")

    # quit app
    def quit_app(self):
        if self.ser:
            self.ser.close()
        if HAS_GPIO:
            GPIO.cleanup()
        self.destroy()
        sys.exit()


# app start
if __name__ == "__main__":
    configure_hc12()               # HC12 config
    OneManStationApp().mainloop()  # main app