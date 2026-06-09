


#terminator def
CRLF = "\r\n"

# Word Index definition
ANGLE_WI = {"21", "22", "24", "25"}                       
DIST_WI  = {"31", "32", "33", "34"}                       
COORD_WI = {"81", "82", "83", "84", "85", "86", "87", "88"}



def password(): # TS motorized function unlock
    return "PASSWORD" + CRLF

def set_terminator_crlf(): # set terminator CRLF
    return "SET/73/1" + CRLF

def set_angle_unit_gon():
    return "SET/40/0" + CRLF      # 0 = Gon 

def set_dist_unit_meter():
    return "SET/41/0" + CRLF     # 0 = Metr 

def set_format_gsi8():
    return "SET/137/0" + CRLF    # 0 = GSI-8 



def beep(on=True):
    return f"SET/30/{1 if on else 0}{CRLF}"

def set_egl(on=True): # EGL 
    return f"SET/35/{1 if on else 0}{CRLF}"

def set_edm_mode(mode=0): # EDM mode
    return f"SET/161/{mode}{CRLF}"


def measure(words=("21", "22", "32")):  # measure (ALL)
    spec = "/".join("WI" + w for w in words)
    return f"GET/M/{spec}{CRLF}"

def get_instant(words): # get last valid values
    spec = "/".join("WI" + w for w in words)
    return f"GET/I/{spec}{CRLF}"



def posit_rel(d_hz, d_v=0): #relative rotation (by defined value)
    return f"POSIT/R/{d_hz}/{d_v}{CRLF}"

def posit_abs(hz, v):  #absolute position 
    return f"POSIT/A/{hz}/{v}{CRLF}"

def posit_search(rng_hz, rng_v): # search in defined range
    return f"POSIT/S/{rng_hz}/{rng_v}{CRLF}"

def change_face(): #change face direction
    return "CFACE" + CRLF


def _put_word(wi, sign, data8, info="...."):
    return f"PUT/{wi}{info}{sign}{data8} {CRLF}"  # GSI-8 PUT slovo: WI(2)+info(4)+sign(1)+data(8)+mezera

def put_point_id(pid): # set point id
    data = str(pid)[-8:].rjust(8, "0")
    return _put_word("11", "+", data)

def put_hz(gon): # set HZ
    val = int(round(abs(gon) * 100000))
    sign = "+" if gon >= 0 else "-"
    return _put_word("21", sign, f"{val:08d}", info="...2")

def put_ppm(ppm): # set ppm
    val = int(round(abs(ppm) * 10000))
    sign = "+" if ppm >= 0 else "-"
    return _put_word("59", sign, f"{val:08d}")

def put_prism_const(mm): # set prism const.
    val = int(round(abs(mm) * 10))
    sign = "+" if mm >= 0 else "-"
    return _put_word("58", sign, f"{val:08d}")



class GSIParser:
 

    def __init__(self):
        self.reset()

    def reset(self):
        self.meas = {}            

    @staticmethod
    def _scale(wi, unit_digit):
        if wi in ANGLE_WI:
            return 1e-5
        return {
            "0": 1e-3, "6": 1e-4, "8": 1e-5,
            "1": 1e-3, "7": 1e-4,
        }.get(unit_digit, 1e-3)

    def feed_line(self, line):  # line 
        line = line.strip()
        if not line:
            return {}
        # errors
        if line.startswith("@"):
            return {"error": line}
        # OK status confirm
        if line == "?":
            return {"ack": True}

        decoded = {}
        for token in line.split():
            #   GSI-8  = 2+4+1+8  = 15 char (8 values)
            #   GSI-16 = 2+4+1+16 = 23 char (16 values)
            w = token.lstrip("*")
            if len(w) >= 23:
                raw = w[7:23]
            elif len(w) >= 15:
                raw = w[7:15]
            else:
                continue
            wi = w[0:2]
            unit_digit = w[5]
            sign = w[6]

            # Alfanumerick to string
            if not raw.lstrip("+-").isdigit():
                self.meas[wi] = (sign + raw).lstrip("0+") or "0"
                decoded[wi] = self.meas[wi]
                continue
            try:
                value = float(sign + raw) * self._scale(wi, unit_digit)
            except ValueError:
                continue
            self.meas[wi] = value
            decoded[wi] = value
        return {"words": decoded}
