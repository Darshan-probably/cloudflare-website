// scripts.js
// In static/javascripts/script.js - Add a reconnection mechanism:
// Add this at the beginning of the file
// scripts.js - Updated to connect to bot server WebSocket
let reconnectAttempts = 0;
const maxReconnectAttempts = 5;
const reconnectInterval = 3000; // 3 seconds

function connectWebSocket() {
    // Get the bot server from a global variable or environment setting
    // This should be injected by the server when rendering the template
    const botServerHost = window.BOT_SERVER_HOST || "de3.bot-hosting.net";
    const botServerPort = window.BOT_SERVER_PORT || "20058";
    
    // Connect directly to the bot server WebSocket
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${protocol}://${botServerHost}:${botServerPort}/ws/nowplaying`);
    
    ws.onopen = () => {
      console.log("WebSocket connected to bot server for updates.");
      reconnectAttempts = 0; // Reset reconnect attempts on successful connection
      // Request current status
      ws.send(JSON.stringify({ action: "status_request" }));
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log("Received WebSocket message:", data.type);
        
        if (data.type === "now_playing") {
          // Update now playing UI elements
          document.getElementById("track-title").textContent = data.title || "No track playing";
          document.getElementById("track-artist").textContent = data.artist || "";
          if (data.thumbnail) {
            document.getElementById("album-art").src = "/static/images/Speechless.png";
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
            queueDiv.innerHTML = data.queue.map(song => `<p>${song.title} - ${song.artist}</p>`).join('');
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
        console.log(`Attempting to reconnect (${reconnectAttempts}/${maxReconnectAttempts})...`);
        setTimeout(connectWebSocket, reconnectInterval);
      } else {
        console.log("Maximum reconnection attempts reached.");
      }
    };
    
    return ws;
}

// Initialize WebSocket connection
const ws = connectWebSocket();
// 1. WebSocket for now playing & queue updates
const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';

ws.onopen = () => {
  console.log("WebSocket connected for updates.");
  // Optionally request current status
  ws.send(JSON.stringify({ action: "status_request" }));
};

// In static/javascripts/script.js - Update the ws.onmessage handler:
ws.onmessage = (event) => {
  try {
    const data = JSON.parse(event.data);
    if (data.type === "now_playing") {
      // Update now playing UI elements
      document.getElementById("track-title").textContent = data.title || "No track playing";
      document.getElementById("track-artist").textContent = data.artist || "";
      
      // Always use the Speechless.png image
      document.getElementById("album-art").src = "/static/images/Speechless.png";
      
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
        queueDiv.innerHTML = data.queue.map(song => `<p>${song.title} - ${song.artist}</p>`).join('');
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
  // Optionally implement reconnection logic if needed.
};
// Add this to static/javascripts/script.js
// Update progress bar with actual track position
let progressInterval;
function updateProgressBar(duration) {
    // Clear any existing interval
    if (progressInterval) clearInterval(progressInterval);
    
    // Don't set up progress if no track is playing
    if (!duration) return;
    
    let startTime = Date.now();
    const progressBar = document.getElementById("progress");
    
    // Update every second
    progressInterval = setInterval(() => {
        const elapsedSeconds = (Date.now() - startTime) / 1000;
        const percentage = Math.min((elapsedSeconds / duration) * 100, 100);
        
        if (progressBar) {
            progressBar.style.width = `${percentage}%`;
        }
        
        // Stop when we reach the end of the track
        if (percentage >= 100) {
            clearInterval(progressInterval);
        }
    }, 1000);
}

// 2. Control Commands via HTTP POST
async function sendControlCommand(action, payload = {}) {
  try {
    const response = await fetch(`/control/${action}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error(`Control command failed: ${action}`);
    console.log(`Control command "${action}" sent successfully.`);
  } catch (error) {
    console.error("Error sending control command:", error);
  }
}

// Called by control buttons in the UI
function handleControl(action) {
  sendControlCommand(action);
}

// 3. Search Functionality and Suggestions

// Create and insert suggestions container below the search input if not exists
function createSuggestionsContainer() {
  let suggestionsContainer = document.getElementById("suggestions-container");
  if (!suggestionsContainer) {
    suggestionsContainer = document.createElement("div");
    suggestionsContainer.id = "suggestions-container";
    suggestionsContainer.classList.add("suggestions"); // Style this class in CSS
    const searchForm = document.getElementById("search-form");
    searchForm.parentNode.insertBefore(suggestionsContainer, searchForm.nextSibling);
  }
  return suggestionsContainer;
}

// Fix the URL in the fetchSuggestions function in static/javascripts/script.js
async function fetchSuggestions(query) {
  try {
    const response = await fetch(`/ws/search/suggestions?query=${encodeURIComponent(query)}`);
    if (!response.ok) throw new Error("Suggestion fetch failed");
    return await response.json();
  } catch (error) {
    console.error("Error fetching suggestions:", error);
    return [];
  }
}
// Handle input events on search field for suggestions
const searchInput = document.getElementById("search-input");
if (searchInput) {
  const suggestionsContainer = createSuggestionsContainer();

  searchInput.addEventListener("input", async () => {
    const query = searchInput.value.trim();
    if (!query) {
      suggestionsContainer.innerHTML = "";
      return;
    }
    const suggestions = await fetchSuggestions(query);
    if (suggestions.length > 0) {
      suggestionsContainer.innerHTML = suggestions
        .map(item => `<div class="suggestion-item">${item}</div>`)
        .join("");
    } else {
      suggestionsContainer.innerHTML = "";
    }

    // Set up click events on suggestion items
    document.querySelectorAll(".suggestion-item").forEach(item => {
      item.addEventListener("click", () => {
        searchInput.value = item.textContent;
        suggestionsContainer.innerHTML = "";
      });
    });
  });
}

const searchForm = document.getElementById("search-form");
if (searchForm) {
  searchForm.addEventListener("submit", async (event) => {
    event.preventDefault();  // Stop the default form submission
    const query = document.getElementById("search-input").value.trim();
    if (!query) return;
    
    try {
      const response = await fetch(`/control/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });
      if (!response.ok) throw new Error("Search failed");
      const data = await response.json();
      console.log("Search response:", data);
      // Optionally update your UI with the search result.
    } catch (error) {
      console.error("Error during search:", error);
    }
  });
}
