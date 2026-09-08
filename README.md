# KitCoek-s_Chatbot
# KITCOEK Assistant — Setup

This project has two parts:

1. **Frontend** — `login.html`, `index.html`, `style.css`, `login.css`, `script.js`, `login.js`
2. **Backend** — `server/` folder, a small Node/Express server that talks to the Anthropic API and keeps your API key private.

The frontend never calls Anthropic directly (that would expose your API key to anyone using the site). Instead it calls your own server at `/api/chat`, and the server calls Anthropic.

## 1. Get an API key

Sign up / log in at https://console.anthropic.com/ and create an API key.

## 2. Set up the backend

```bash
cd server
npm install
cp .env.example .env
```

Open `.env` and paste your key:

```
ANTHROPIC_API_KEY=sk-ant-...
PORT=3000
```

Start the server:

```bash
npm start
```

You should see:
```
KITCOEK Assistant backend running on http://localhost:3000
```

## 3. Serve the frontend

The frontend files (`login.html`, `index.html`, etc.) need to be served from the **same origin** as the backend so `fetch('/api/chat')` reaches it, and so the browser doesn't block the request as cross-origin.

Simplest way: put the frontend files in a `public/` folder next to `server.js`, then add one line to `server.js`:

```js
app.use(express.static('public'));
```

Then visit `http://localhost:3000/login.html` in your browser.

(Alternative: keep them separate and change the `fetch('/api/chat')` call in `script.js` to your server's full URL, e.g. `fetch('http://localhost:3000/api/chat')` — but then you'll need to enable CORS for your frontend's origin specifically, which the current `cors()` setup already allows for any origin during development.)

## 4. Customize the assistant's knowledge

Open `server/server.js` and edit `SYSTEM_PROMPT`. This is where you should add:
- Real deadlines and dates
- Actual department contact details and links
- Specific KITCOEK policies

The model will only be accurate about things you tell it here — it doesn't know your college's specific data on its own.

## 5. Fallback behavior

If the backend is down or the API call fails, `script.js` automatically falls back to the built-in canned answers (`knowledge` array) so the chat doesn't break — it just uses simpler, static replies until the backend is back.

## Using n8n instead of the Node server

Instead of `server/`, you can use n8n as the entire backend:

1. Build a workflow: Webhook (path `/kitcoek-chat`) → Anthropic node (or HTTP Request to `api.anthropic.com`) → Respond to Webhook, returning `{ "reply": "..." }`.
2. Build a second workflow for login: Webhook (path `/kitcoek-login`) → check the PRN against a Google Sheets/database node → Respond to Webhook with `{ "valid": true/false, "name": "..." }`.
3. Activate both workflows in n8n to get their permanent (non-"test") URLs.
4. In `script.js`, set `N8N_CHAT_WEBHOOK_URL` to your chat webhook URL.
5. In `login.js`, set `N8N_LOGIN_WEBHOOK_URL` to your login webhook URL. If you leave this as the placeholder, login skips the real check and only validates the PRN's format.

With this setup you don't need `server/` at all — the frontend files can be hosted anywhere (even a static file host) since they call n8n directly instead of a local API route.

## Deploying for real students

For a live site, you'll additionally want to:
- Deploy the backend somewhere (Render, Railway, a VPS, etc.) rather than `localhost`.
- Validate PRNs against your actual student database instead of just format-checking them.
- Add rate limiting to `/api/chat` so the API can't be abused.
- Serve the frontend over HTTPS.
