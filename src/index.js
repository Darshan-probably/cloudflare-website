import { Router } from 'itty-router';
import { createCors } from 'itty-cors';

// Environment variables to be set in Cloudflare dashboard:
// API_SECRET, SESSION_SECRET, MAIN_SERVER_URL, DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DISCORD_REDIRECT_URI

// CORS configuration
const { preflight, corsify } = createCors({
  origins: ['*'], // In production, specify your exact domain
  methods: ['GET', 'POST', 'OPTIONS'],
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer',
    'x-api-token': true
  }
});

// Create router
const router = Router();

// Session management
class SessionManager {
  constructor(SECRET) {
    this.SECRET = SECRET;
  }

  async encrypt(data) {
    const encoder = new TextEncoder();
    const encoded = encoder.encode(JSON.stringify(data));
    
    // Use SubtleCrypto for encryption (simplified for example)
    // In production, consider using jose library for JWE
    const key = await crypto.subtle.importKey(
      "raw",
      encoder.encode(this.SECRET),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"]
    );
    
    const signature = await crypto.subtle.sign(
      "HMAC",
      key,
      encoded
    );
    
    return {
      data: btoa(JSON.stringify(data)),
      sig: btoa(String.fromCharCode(...new Uint8Array(signature)))
    };
  }
  
  async decrypt(cookie) {
    try {
      if (!cookie) return null;
      
      const { data, sig } = JSON.parse(atob(cookie));
      const sessionData = JSON.parse(atob(data));
      
      // In a real implementation, verify the signature here
      
      return sessionData;
    } catch (e) {
      return null;
    }
  }
  
  async createSessionCookie(data) {
    const session = await this.encrypt(data);
    return `session=${btoa(JSON.stringify(session))}; HttpOnly; Secure; SameSite=Lax; Path=/`;
  }
  
  getSessionFromRequest(request) {
    const cookies = request.headers.get('Cookie') || '';
    const sessionCookie = cookies.split(';')
      .map(c => c.trim())
      .find(c => c.startsWith('session='));
      
    if (!sessionCookie) return null;
    
    const sessionValue = sessionCookie.split('=')[1];
    return this.decrypt(sessionValue);
  }
}

// Auth handlers
async function handleOAuthCallback(request, env) {
  const url = new URL(request.url);
  const code = url.searchParams.get('code');
  
  if (!code) {
    return new Response('No code provided', { status: 400 });
  }
  
  // Exchange code for token
  const tokenResponse = await fetch('https://discord.com/api/oauth2/token', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    },
    body: new URLSearchParams({
      client_id: env.DISCORD_CLIENT_ID,
      client_secret: env.DISCORD_CLIENT_SECRET,
      grant_type: 'authorization_code',
      code,
      redirect_uri: env.DISCORD_REDIRECT_URI,
      scope: 'identify'
    })
  });
  
  const tokenData = await tokenResponse.json();
  
  if (!tokenData.access_token) {
    return new Response('Failed to get access token', { status: 400 });
  }
  
  // Get user info
  const userResponse = await fetch('https://discord.com/api/users/@me', {
    headers: {
      Authorization: `Bearer ${tokenData.access_token}`
    }
  });
  
  const userData = await userResponse.json();
  
  // Create session
  const sessionManager = new SessionManager(env.SESSION_SECRET);
  const user = {
    username: userData.username,
    avatar: userData.avatar,
    id: userData.id,
    avatar_url: `https://cdn.discordapp.com/avatars/${userData.id}/${userData.avatar}.png`
  };
  
  const sessionCookie = await sessionManager.createSessionCookie(user);
  
  // Redirect to home page
  return new Response(null, {
    status: 302,
    headers: {
      Location: '/',
      'Set-Cookie': sessionCookie
    }
  });
}

// WebSocket handler
async function handleWebSocket(request, env, ctx) {
  // Check if connection is from bot (has API token)
  const apiToken = request.headers.get('x-api-token');
  const isBot = apiToken === env.API_SECRET;

  // For production, proxy WebSocket to your main server
  const url = new URL(request.url);
  const mainServerUrl = env.MAIN_SERVER_URL;
  const wsEndpoint = `${mainServerUrl.replace('http', 'ws')}/ws/nowplaying`;
  
  // Create WebSocket headers
  const headers = new Headers(request.headers);
  if (isBot) {
    headers.set('x-api-token', env.API_SECRET);
  }
  
  // Forward the WebSocket connection
  return fetch(wsEndpoint, {
    headers,
    body: request.body,
    method: request.method,
    cf: {
      // Enable WebSockets forwarding
      websocket: {
        // This is required for websocket forward
        subprotocols: ['websocket']
      }
    }
  });
}

// Setup routes
router.options('*', preflight);

// WebSocket routes
router.get('/ws/nowplaying', handleWebSocket);

// Auth routes
router.get('/login', (request, env) => {
  const params = new URLSearchParams({
    client_id: env.DISCORD_CLIENT_ID,
    redirect_uri: env.DISCORD_REDIRECT_URI,
    response_type: 'code',
    scope: 'identify'
  });
  
  return new Response(null, {
    status: 302,
    headers: {
      Location: `https://discord.com/api/oauth2/authorize?${params.toString()}`
    }
  });
});

router.get('/oauth-callback', handleOAuthCallback);

router.get('/logout', async (request, env) => {
  return new Response(null, {
    status: 302,
    headers: {
      Location: '/',
      'Set-Cookie': 'session=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0'
    }
  });
});

// API forwarding routes
router.post('/forward_to_bot/:action', async (request, env) => {
  const action = request.params.action;
  try {
    const payload = await request.json();
    const mainServerUrl = env.MAIN_SERVER_URL;
    
    const response = await fetch(`${mainServerUrl}/forward_to_bot/${action}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-token': env.API_SECRET
      },
      body: JSON.stringify(payload)
    });
    
    const data = await response.json();
    return new Response(JSON.stringify(data), {
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    return new Response(JSON.stringify({ error: error.message, status: 'failed' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
});

// Control routes
router.post('/control/:action', async (request, env) => {
  const action = request.params.action;
  try {
    const payload = await request.json();
    const mainServerUrl = env.MAIN_SERVER_URL;
    
    const response = await fetch(`${mainServerUrl}/forward_to_bot/${action}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-token': env.API_SECRET
      },
      body: JSON.stringify(payload)
    });
    
    const data = await response.json();
    return new Response(JSON.stringify(data), {
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    return new Response(JSON.stringify({ error: error.message, status: 'failed' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
});

// Search suggestions
router.get('/search/suggestions', async (request, env) => {
  const url = new URL(request.url);
  const query = url.searchParams.get('query');
  
  if (!query) {
    return new Response(JSON.stringify([]), {
      headers: { 'Content-Type': 'application/json' }
    });
  }
  
  // If it's a URL, offer simple suggestion
  if (query.startsWith('http')) {
    return new Response(JSON.stringify(['Play this URL']), {
      headers: { 'Content-Type': 'application/json' }
    });
  }
  
  // For non-URLs, offer generic suggestions
  const suggestions = [
    `${query} - Official Video`,
    `${query} - Audio`,
    `${query} - Live Performance`
  ];
  
  return new Response(JSON.stringify(suggestions), {
    headers: { 'Content-Type': 'application/json' }
  });
});

// Serve static files and HTML templates
router.get('/', async (request, env) => {
  const sessionManager = new SessionManager(env.SESSION_SECRET);
  const user = await sessionManager.getSessionFromRequest(request);
  
  // Render template - in a real app, use an HTML template library
  // For simplicity, we'll use basic string interpolation here

  return new Response(generateIndexHtml(user), {
    headers: { 'Content-Type': 'text/html' }
  });
});

// Static assets handler - simplified for this example
router.get('/static/*', async (request) => {
  const url = new URL(request.url);
  const path = url.pathname.replace('/static/', '');
  
  // In a real implementation, you'd use KV storage or another method to serve static files
  // This is just a placeholder to show the concept
  if (path.endsWith('.css')) {
    return new Response(CSS_CONTENT, {
      headers: { 'Content-Type': 'text/css' }
    });
  } else if (path.endsWith('.js')) {
    return new Response(JS_CONTENT, {
      headers: { 'Content-Type': 'application/javascript' }
    });
  } else if (path.endsWith('.png')) {
    // For images, you'd return actual binary data
    return new Response('Image data would go here', {
      headers: { 'Content-Type': 'image/png' }
    });
  }
  
  return new Response('Not found', { status: 404 });
});

// 404 handler
router.all('*', () => new Response('Not Found', { status: 404 }));

// Main fetch handler
export default {
  async fetch(request, env, ctx) {
    // Handle the request with our router
    return router.handle(request, env, ctx).catch(error => {
      return new Response(`Server Error: ${error.message}`, { status: 500 });
    }).then(corsify);
  }
};

// Template functions - in a real app, use a template engine
function generateIndexHtml(user) {
  // This is a simplified example - in a real app, use proper templating
  const userSection = user ? 
    `<section class="search-section">
      <form id="search-form" method="POST" onsubmit="return false;">
        <input type="text" id="search-input" placeholder="Search for a track..." required>
        <button type="submit" id="search-btn">Search</button>
      </form>
    </section>

    <section class="player-container">
      <div class="now-playing">
        <h2>Now Playing</h2>
        <div class="track-info">
          <img id="album-art" src="https://i.imgur.com/opTLRNC.png" alt="Album Art">
          <div class="track-details">
            <h3 id="track-title">No track playing</h3>
            <p id="track-artist"></p>
            <div class="progress-bar">
              <div id="progress" class="progress"></div>
            </div>
          </div>
        </div>
      </div>
      
      <div class="queue-section">
        <h2>Queue</h2>
        <div id="queue">
          <p>No songs in queue.</p>
        </div>
      </div>
      
      <div class="controls">
        <button class="control-btn" onclick="handleControl('previous')">Previous</button>
        <button class="control-btn" onclick="handleControl('play_pause')">Play/Pause</button>
        <button class="control-btn" onclick="handleControl('skip')">Skip</button>
        <button class="control-btn" onclick="handleControl('loop')">Loop</button>
        <button class="control-btn" onclick="handleControl('shuffle')">Shuffle</button>
        <button class="control-btn" onclick="handleControl('stop')">Stop</button>
      </div>
    </section>` :
    `<section class="about">
      <h2>Welcome to Speechless!</h2>
      <p>Speechless is a feature-rich Discord music bot that brings people together through music. Log in to control playback, search for tracks, and see what's playing in real time.</p>
      <a href="/login" class="login-button">Login to Get Started</a>
    </section>`;

  const userNav = user ?
    `<div class="dropdown">
      <button class="dropbtn">
        <div class="user-info">
          <img src="${user.avatar_url}" alt="User Avatar" class="user-avatar">
          <span>${user.username}</span>
        </div>
      </button>
      <div class="dropdown-content">
        <a href="/logout">Logout</a>
      </div>
    </div>` :
    `<a href="/login" class="login-button">Login</a>`;

  const scripts = user ? '<script src="/static/javascripts/script.js"></script>' : '';

  return `<!DOCTYPE html>
<html lang="en" class="bg-gray-900 text-gray-200">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Speechless - Discord Music Bot</title>
  <link rel="stylesheet" href="/static/css/styles.css">
</head>
<body>
  <nav class="navbar">
    <div class="navbar-brand">Speechless</div>
    <div class="navbar-links">
      <a href="/docs" class="docs-button">Docs</a>
      ${userNav}
    </div>
  </nav>

  <div class="container">
    ${userSection}
  </div>

  <footer class="footer">
    <a href="https://github.com/Darshan-probably" target="_blank">
      <img src="/static/images/github-mark.png" alt="GitHub" class="github-logo">
    </a>
  </footer>

  ${scripts}
</body>
</html>`;
}

// Static content placeholders - in a real app, these would be stored in KV or another storage
const CSS_CONTENT = `:root {
  --primary-color: #7289da;
  --background-dark: #18191c;
  --background-light: #2f3136;
  --text-primary: #ffffff;
  --text-secondary: #b9bbbe;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
  font-family: 'Arial', sans-serif;
}

body {
  background-color: var(--background-dark);
  color: var(--text-primary);
  min-height: 100vh;
}

/* Navbar Styles */
.navbar {
  background-color: var(--background-light);
  padding: 1rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 2px 5px rgba(0,0,0,0.2);
}

.navbar-brand {
  font-size: 1.5rem;
  font-weight: bold;
  color: var(--primary-color);
}

.navbar-links {
  display: flex;
  gap: 1.5rem;
  align-items: center;
}

.login-button, .docs-button {
  padding: 0.5rem 1rem;
  border-radius: 4px;
  text-decoration: none;
  color: var(--text-primary);
  transition: background-color 0.3s;
}

.login-button {
  background-color: var(--primary-color);
}

.login-button:hover {
  background-color: #5b6eae;
}

/* More CSS content would go here */`;

const JS_CONTENT = `// WebSocket for now playing & queue updates
let reconnectAttempts = 0;
const maxReconnectAttempts = 5;
const reconnectInterval = 3000; // 3 seconds

function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(\`\${protocol}://\${window.location.host}/ws/nowplaying\`);
  
  ws.onopen = () => {
    console.log("WebSocket connected for updates.");
    reconnectAttempts = 0; // Reset reconnect attempts on successful connection
    // Request current status
    ws.send(JSON.stringify({ action: "status_request" }));
  };
  
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === "now_playing") {
        // Update now playing UI elements
        document.getElementById("track-title").textContent = data.title || "No track playing";
        document.getElementById("track-artist").textContent = data.artist || "";
        if (data.thumbnail) {
          document.getElementById("album-art").src = data.thumbnail;
        }
        
        // Reset progress bar
        const progressBar = document.getElementById("progress");
        if (progressBar) progressBar.style.width = "0%";
        
        // Start progress tracking if we have duration
        if (data.duration > 0) {
          updateProgressBar(data.duration);
        }
      } else if (data.type === "queue_update") {
        // Update queue display
        const queueDiv = document.getElementById("queue");
        if (data.queue && data.queue.length > 0) {
          queueDiv.innerHTML = data.queue.map(song => \`<p>\${song.title} - \${song.artist}</p>\`).join('');
        } else {
          queueDiv.innerHTML = "<p>No songs in queue.</p>";
        }
      }
    } catch (error) {
      console.error("Error parsing WebSocket message:", error);
    }
  };
  
  ws.onerror = (err) => {
    console.error("WebSocket error:", err);
  };
  
  ws.onclose = () => {
    console.log("WebSocket connection closed.");
    // Try to reconnect
    if (reconnectAttempts < maxReconnectAttempts) {
      reconnectAttempts++;
      console.log(\`Attempting to reconnect (\${reconnectAttempts}/\${maxReconnectAttempts})...\`);
      setTimeout(connectWebSocket, reconnectInterval);
    } else {
      console.log("Maximum reconnection attempts reached.");
    }
  };
  
  return ws;
}

// Initialize WebSocket connection
const ws = connectWebSocket();

// More JavaScript code would go here`;