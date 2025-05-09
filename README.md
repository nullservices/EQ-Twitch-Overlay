# 🎮 EQ-Style Twitch Chat Overlay

A nostalgic EverQuest-inspired Twitch chat overlay for streamers and roleplayers.

This overlay mimics the classic EQ chat window style — complete with draggable/resizable UI, retro fonts, and Twitch chat integration. No command line needed. Just authenticate and go!

![Demo](./eq_chat_overlay_demo.gif)

---

## ✨ Features

- ✅ Retro EQ-style look and feel
- ✅ Draggable window (click and drag anywhere)
- ✅ Twitch chat viewer & sender
- ✅ Built-in OAuth login via browser
- ✅ Emote filtering (only shows clean text lines)
- ✅ Right-click menu:
  - **Resize** – enables window borders to freely resize
  - **Close** – exits the overlay
- ✅ Overlay mode automatically returns when you hit `Enter` or `Escape`

---

## 🛠 How to Use

### 1. Register with Twitch

Only required once by the developer (not end-users):

- Go to [Twitch Dev Console](https://dev.twitch.tv/console/apps)
- Click **Register Your Application**
  - Name: `EQChatOverlay`
  - OAuth Redirect URL: `http://localhost:8080`
  - Category: `Chat Bot`
- Copy the **Client ID** and paste it into the script at:

```python
CLIENT_ID = 'your-client-id-here'
