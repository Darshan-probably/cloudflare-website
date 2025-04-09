// scripts.js

// 1. WebSocket for now playing & queue updates
const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
const ws = new WebSocket(`${protocol}://${window.location.host}/ws/nowplaying`);

ws.onopen = () => {
  console.log("WebSocket connected for updates.");
  // Optionally request current status
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
      // Optionally update progress bar etc.
    } else if (data.type === "queue_update") {
      // Update queue display
      const queueDiv = document.getElementById("queue");
      if (data.queue && data.queue.length > 0) {
        queueDiv.innerHTML = data.queue.map(song => `<p>${song}</p>`).join('');
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
