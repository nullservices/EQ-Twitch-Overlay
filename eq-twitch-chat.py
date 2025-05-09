import tkinter as tk
from PIL import Image, ImageTk
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import webbrowser
import requests
from irc.client import SimpleIRCClient
import time

# === TWITCH API CREDENTIALS ===
# To allow users to authenticate with their own Twitch account, this app uses Twitch's
# implicit OAuth flow (no password or secret needed).
#
# You must register this application with Twitch to get a CLIENT_ID:
#
# 1. Visit: https://dev.twitch.tv/console/apps
# 2. Click “Register Your Application”
# 3. Fill out the form:
#    - Name: EQChatOverlay (or anything you like)
#    - OAuth Redirect URL: http://localhost:8080
#    - Category: Chat Bot
# 4. After creating it, copy the generated CLIENT ID and paste it below.
#
# After authorizing, the app automatically retrieves their token and connects to chat.
#
# This CLIENT_ID is safe to share — do NOT include a client secret (not needed).

# === CONFIG ===
CLIENT_ID = 'INPUT CLIENT ID' #Input your client id from the twitch app you made above
REDIRECT_URI = 'http://localhost:8080'
SCOPES = 'chat:read chat:edit'
TWITCH_CHANNEL = 'INPUT TWITCH USERNAME' #Input your twitch username
ASSETS_DIR = 'assets'

oauth_token = None
twitch_username = None
irc_connection = None

# === OAUTH ===
class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global oauth_token
        if "access_token" in self.path:
            query = self.path.split("?")[1]
            params = dict(qc.split("=") for qc in query.split("&"))
            oauth_token = params.get("access_token")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h1>You may now close this window.</h1>")
            threading.Thread(target=self.server.shutdown).start()
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<script>const p=new URLSearchParams(location.hash.substr(1));location=`http://localhost:8080/?${p}`</script>")

def get_oauth_token():
    global oauth_token, twitch_username
    server = HTTPServer(("localhost", 8080), OAuthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    webbrowser.open(
        f"https://id.twitch.tv/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=token&scope={SCOPES}"
    )
    while oauth_token is None:
        pass
    headers = {"Authorization": f"OAuth {oauth_token}"}
    resp = requests.get("https://id.twitch.tv/oauth2/validate", headers=headers)
    if resp.status_code == 200:
        twitch_username = resp.json().get("login")
    else:
        twitch_username = "anonymous"
    return oauth_token

# === IRC ===
class TwitchChatClient(SimpleIRCClient):
    def __init__(self, on_message, token):
        super().__init__()
        self.on_message = on_message
        self.token = token

    def on_welcome(self, conn, event):
        global irc_connection
        irc_connection = conn
        conn.cap("REQ", ":twitch.tv/tags")
        conn.join(f"#{TWITCH_CHANNEL}")

    def on_pubmsg(self, conn, event):
        tags = {tag['key']: tag['value'] for tag in getattr(event, 'tags', [])}
        msg = event.arguments[0]
        name = event.source.nick
        self.on_message(name, msg, tags)

    def run(self):
        self.connect("irc.chat.twitch.tv", 6667, twitch_username, password=f"oauth:{self.token}")
        self.start()

# === EQ-STYLE OVERLAY ===
class EQChatWindow:
    def __init__(self, token):
        self.token = token
        self.root = tk.Tk()
        self.root.geometry("420x320")
        self.root.title("EQ Twitch Chat")
        self.root.attributes("-topmost", True)

        self.is_overlay_mode = True

        # Background
        self.bg_raw = Image.open(os.path.join(ASSETS_DIR, 'wnd_bg_dark_rock.png'))
        self.bg_img = ImageTk.PhotoImage(self.bg_raw.resize((420, 320)))
        self.bg_label = tk.Label(self.root, image=self.bg_img, bd=0)
        self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)

        # Canvas for title + drag
        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.do_drag)
        self.canvas.bind("<Button-3>", self.show_menu)

        # Blue header bar
        self.title_bar_rect = self.canvas.create_rectangle(6, 6, 414, 26, fill="#223344", outline="#111111")
        self.title_text = self.canvas.create_text(210, 16, text="Twitch Chat", fill="white", font=("Segoe UI", 10))

        # Chat display
        self.text_area = tk.Text(self.root, bg="black", fg="#00FF00",
                                 font=("Courier New", 9), relief=tk.FLAT, wrap=tk.WORD)
        self.text_area.place(x=10, y=30, width=400, height=230)
        self.text_area.config(state=tk.DISABLED)

        self.scrollbar = tk.Scrollbar(self.root, command=self.text_area.yview,
                                      bg="black", troughcolor="black", highlightthickness=0)
        self.scrollbar.place(x=410, y=30, height=230)
        self.text_area.config(yscrollcommand=self.scrollbar.set)

        # Entry
        self.entry_var = tk.StringVar()
        self.entry = tk.Entry(self.root, textvariable=self.entry_var,
                              bg="#111111", fg="#00FF00", font=("Courier New", 9),
                              insertbackground="#00FF00", relief=tk.FLAT)
        self.entry.place(x=10, y=270, width=400, height=20)
        self.entry.bind("<Return>", self.send_message)

        # Resize mode label
        self.resize_label = tk.Label(self.root,
            text="🖱 Resize the window. Press Enter to confirm or Esc to cancel.",
            bg="#223344", fg="white", font=("Segoe UI", 9), bd=1, relief=tk.SOLID)
        self.resize_label.place_forget()

        # Menu
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Resize", command=self.enable_resize_mode)
        self.menu.add_command(label="Close", command=self.root.destroy)

        self.root.bind("<Escape>", lambda e: self.apply_overlay_mode())
        self.root.bind("<Return>", lambda e: self.apply_overlay_mode())
        self.root.bind("<Configure>", self.on_resize)

        self.start_irc_thread(token)
        self.apply_overlay_mode()

    def show_menu(self, event):
        self.menu.tk_popup(event.x_root, event.y_root)

    def enable_resize_mode(self):
        self.root.overrideredirect(False)
        self.is_overlay_mode = False
        self.resize_label.place(relx=0.5, rely=0.5, anchor="center")

    def apply_overlay_mode(self):
        self.root.overrideredirect(True)
        self.is_overlay_mode = True
        self.resize_label.place_forget()

    def start_drag(self, event):
        if not self.is_overlay_mode:
            return
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def do_drag(self, event):
        if not self.is_overlay_mode:
            return
        x = self.root.winfo_pointerx() - self._drag_start_x
        y = self.root.winfo_pointery() - self._drag_start_y
        self.root.geometry(f"+{x}+{y}")

    def on_resize(self, event):
        w, h = self.root.winfo_width(), self.root.winfo_height()
        try:
            self.bg_img = ImageTk.PhotoImage(self.bg_raw.resize((w, h)))
            self.bg_label.config(image=self.bg_img)
            self.text_area.place(x=10, y=30, width=w - 30, height=h - 90)
            self.scrollbar.place(x=w - 20, y=30, height=h - 90)
            self.entry.place(x=10, y=h - 40, width=w - 30, height=20)
            self.canvas.coords(self.title_bar_rect, 6, 6, w - 6, 26)
            self.canvas.coords(self.title_text, w // 2, 16)
        except:
            pass

    def start_irc_thread(self, token):
        client = TwitchChatClient(self.add_message, token)
        threading.Thread(target=client.run, daemon=True).start()

    def add_message(self, user, msg, tags):
        if tags.get("emotes"):
            return
        self.text_area.config(state=tk.NORMAL)
        self.text_area.insert(tk.END, f"<{user}> {msg}\n")
        self.text_area.see(tk.END)
        self.text_area.config(state=tk.DISABLED)

    def send_message(self, event=None):
        global irc_connection, twitch_username
        msg = self.entry_var.get().strip()
        if msg and irc_connection:
            irc_connection.privmsg(f"#{TWITCH_CHANNEL}", msg)
            self.add_message(twitch_username, msg, {})
            self.entry_var.set("")

    def run(self):
        self.root.mainloop()

# === RUN ===
if __name__ == "__main__":
    token = get_oauth_token()
    EQChatWindow(token).run()
