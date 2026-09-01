// Veritas AI Vanilla Frontend Controller
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
import { getAuth, GoogleAuthProvider, signInWithPopup, onAuthStateChanged, signOut } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-auth.js";

// Firebase Configuration for veritas-ai-a08ec
const firebaseConfig = {
  apiKey: "AIzaSyDUmHGnORCfv8wJJLNJg3bkbje14azbxNE",
  authDomain: "veritas-ai-a08ec.firebaseapp.com",
  projectId: "veritas-ai-a08ec",
  storageBucket: "veritas-ai-a08ec.firebasestorage.app",
  messagingSenderId: "246311189482",
  appId: "1:246311189482:web:461a7ab44c5f6e256c1093"
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const googleProvider = new GoogleAuthProvider();
googleProvider.setCustomParameters({ prompt: "select_account" });

let authToken = localStorage.getItem("veritas_token") || null;
let currentConvId = null;
let selectedUploadFile = null;

// DOM Elements
const authSection = document.getElementById("authSection");
const navTabs = document.getElementById("navTabs");
const navUser = document.getElementById("navUser");
const userEmailBadge = document.getElementById("userEmailBadge");
const logoutBtn = document.getElementById("logoutBtn");
const googleSignInBtn = document.getElementById("googleSignInBtn");

// Tab switching
function switchTab(tabId) {
  document.querySelectorAll(".app-tab").forEach(el => el.style.display = "none");
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.tab === tabId);
  });

  const targetTab = document.getElementById(`${tabId}Tab`);
  if (targetTab) targetTab.style.display = tabId === "chat" ? "grid" : "block";

  if (tabId === "dashboard") loadDashboard();
  if (tabId === "chat") loadConversations();
  if (tabId === "documents") loadDocuments();
}

window.switchTab = switchTab;

document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});

// Google Sign-In Handler
if (googleSignInBtn) {
  googleSignInBtn.addEventListener("click", async () => {
    authAlert.style.display = "none";
    try {
      const result = await signInWithPopup(auth, googleProvider);
      const idToken = await result.user.getIdToken();
      authToken = idToken;
      localStorage.setItem("veritas_token", authToken);
      localStorage.setItem("veritas_user", result.user.email);
      initLoggedInState(result.user.email);
    } catch (err) {
      console.error("Google sign in error:", err);
      authAlert.textContent = err.message || "Failed to sign in with Google.";
      authAlert.style.display = "block";
    }
  });
}

// Auth form handling
let isRegisterMode = false;
const showLoginBtn = document.getElementById("showLoginBtn");
const showRegisterBtn = document.getElementById("showRegisterBtn");
const nameGroup = document.getElementById("nameGroup");
const authSubmitBtn = document.getElementById("authSubmitBtn");
const authForm = document.getElementById("authForm");
const authAlert = document.getElementById("authAlert");
const authSuccess = document.getElementById("authSuccess");

showLoginBtn.addEventListener("click", () => {
  isRegisterMode = false;
  showLoginBtn.classList.add("active");
  showRegisterBtn.classList.remove("active");
  nameGroup.style.display = "none";
  authSubmitBtn.textContent = "Sign In";
  authAlert.style.display = "none";
});

showRegisterBtn.addEventListener("click", () => {
  isRegisterMode = true;
  showRegisterBtn.classList.add("active");
  showLoginBtn.classList.remove("active");
  nameGroup.style.display = "block";
  authSubmitBtn.textContent = "Create Account";
  authAlert.style.display = "none";
});

authForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  authAlert.style.display = "none";
  authSuccess.style.display = "none";

  const email = document.getElementById("authEmail").value.trim();
  const password = document.getElementById("authPassword").value;
  const name = document.getElementById("authName").value.trim();

  const endpoint = isRegisterMode ? "/auth/register" : "/auth/login";
  const payload = isRegisterMode ? { name, email, password } : { email, password };

  try {
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Authentication failed.");
    }

    authToken = data.access_token;
    localStorage.setItem("veritas_token", authToken);
    localStorage.setItem("veritas_user", email);

    initLoggedInState(email);
  } catch (err) {
    authAlert.textContent = err.message;
    authAlert.style.display = "block";
  }
});

logoutBtn.addEventListener("click", async () => {
  try {
    await signOut(auth);
  } catch (e) {}
  authToken = null;
  localStorage.removeItem("veritas_token");
  localStorage.removeItem("veritas_user");
  showLoggedOutState();
});

function initLoggedInState(email) {
  authSection.style.display = "none";
  navTabs.style.display = "flex";
  navUser.style.display = "flex";
  userEmailBadge.textContent = email || "User";
  document.getElementById("welcomeText").textContent = `Welcome, ${(email || "User").split("@")[0]}!`;
  switchTab("dashboard");
}

function showLoggedOutState() {
  authSection.style.display = "block";
  navTabs.style.display = "none";
  navUser.style.display = "none";
  document.querySelectorAll(".app-tab").forEach(el => el.style.display = "none");
}

// Check initial session
if (authToken) {
  const savedEmail = localStorage.getItem("veritas_user") || "User";
  initLoggedInState(savedEmail);
} else {
  showLoggedOutState();
}

// Helpers for API requests
async function authFetch(url, options = {}) {
  options.headers = {
    ...options.headers,
    "Authorization": `Bearer ${authToken}`
  };
  const res = await fetch(url, options);
  if (res.status === 401) {
    logoutBtn.click();
    throw new Error("Session expired. Please sign in again.");
  }
  return res;
}

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return "0 KB";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

// 1. DASHBOARD CONTROLLER
async function loadDashboard() {
  try {
    const statsRes = await authFetch("/dashboard/stats");
    if (statsRes.ok) {
      const stats = await statsRes.json();
      document.getElementById("statDocs").textContent = stats.total_documents || 0;
      document.getElementById("statConvs").textContent = stats.total_conversations || 0;
      document.getElementById("statQuestions").textContent = stats.total_questions || 0;
      document.getElementById("statStorage").textContent = formatBytes(stats.total_storage_bytes || 0);
    }

    const docsRes = await authFetch("/dashboard/recent-documents");
    const container = document.getElementById("recentDocsContainer");
    if (docsRes.ok) {
      const docs = await docsRes.json();
      if (!docs || docs.length === 0) {
        container.innerHTML = `<p class="empty-state">No documents uploaded yet. Click <strong>Upload PDF</strong> to begin.</p>`;
      } else {
        container.innerHTML = `
          <table class="data-table">
            <thead>
              <tr><th>Filename</th><th>Status</th><th>Size</th><th>Uploaded</th></tr>
            </thead>
            <tbody>
              ${docs.map(d => `
                <tr>
                  <td><strong>📄 ${d.filename}</strong></td>
                  <td><span class="badge ${d.status === 'processed' ? 'badge-success' : 'badge-warning'}">${d.status}</span></td>
                  <td>${formatBytes(d.file_size)}</td>
                  <td>${new Date(d.uploaded_at).toLocaleDateString()}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        `;
      }
    }
  } catch (err) {
    console.error("Dashboard error:", err);
  }
}

window.loadDashboard = loadDashboard;

// 2. UPLOAD CONTROLLER
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const selectedFileInfo = document.getElementById("selectedFileInfo");
const selectedFileName = document.getElementById("selectedFileName");
const selectedFileSize = document.getElementById("selectedFileSize");
const startUploadBtn = document.getElementById("startUploadBtn");
const uploadProgress = document.getElementById("uploadProgress");
const uploadAlert = document.getElementById("uploadAlert");
const uploadSuccess = document.getElementById("uploadSuccess");

fileInput.addEventListener("change", (e) => {
  if (e.target.files && e.target.files[0]) {
    setUploadFile(e.target.files[0]);
  }
});

dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.style.borderColor = "var(--primary)";
});

dropzone.addEventListener("dragleave", () => {
  dropzone.style.borderColor = "var(--border-color)";
});

dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.style.borderColor = "var(--border-color)";
  if (e.dataTransfer.files && e.dataTransfer.files[0]) {
    setUploadFile(e.dataTransfer.files[0]);
  }
});

function setUploadFile(file) {
  uploadAlert.style.display = "none";
  uploadSuccess.style.display = "none";

  if (!file.name.toLowerCase().endsWith(".pdf")) {
    uploadAlert.textContent = "Please select a valid PDF file.";
    uploadAlert.style.display = "block";
    return;
  }

  selectedUploadFile = file;
  selectedFileName.textContent = file.name;
  selectedFileSize.textContent = formatBytes(file.size);
  selectedFileInfo.style.display = "flex";
  startUploadBtn.style.display = "inline-flex";
}

startUploadBtn.addEventListener("click", async () => {
  if (!selectedUploadFile) return;

  uploadAlert.style.display = "none";
  uploadSuccess.style.display = "none";
  uploadProgress.style.display = "flex";
  startUploadBtn.disabled = true;

  const formData = new FormData();
  formData.append("file", selectedUploadFile);

  try {
    const res = await authFetch("/upload", {
      method: "POST",
      body: formData
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed.");

    uploadSuccess.innerHTML = `<strong>Success!</strong> ${data.filename} processed and indexed into FAISS vector database.`;
    uploadSuccess.style.display = "block";
    selectedUploadFile = null;
    selectedFileInfo.style.display = "none";
    startUploadBtn.style.display = "none";
    fileInput.value = "";
  } catch (err) {
    uploadAlert.textContent = err.message;
    uploadAlert.style.display = "block";
  } finally {
    uploadProgress.style.display = "none";
    startUploadBtn.disabled = false;
  }
});

// 3. CHAT CONTROLLER
const convList = document.getElementById("convList");
const chatMessages = document.getElementById("chatMessages");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const newChatBtn = document.getElementById("newChatBtn");
const chatTitle = document.getElementById("chatTitle");

async function loadConversations() {
  try {
    const res = await authFetch("/conversations");
    if (res.ok) {
      const convs = await res.json();
      if (!convs || convs.length === 0) {
        convList.innerHTML = `<p class="empty-state">No sessions yet.</p>`;
      } else {
        convList.innerHTML = convs.map(c => `
          <div class="conv-item ${c.id === currentConvId ? 'active' : ''}" onclick="selectConversation('${c.id}', '${c.title}')">
            <span>💬 ${c.title || 'Chat'}</span>
            <button class="btn btn-danger btn-sm" onclick="deleteConversation('${c.id}', event)">✕</button>
          </div>
        `).join("");

        if (!currentConvId && convs.length > 0) {
          selectConversation(convs[0].id, convs[0].title);
        }
      }
    }
  } catch (err) {
    console.error("Conversations error:", err);
  }
}

window.loadConversations = loadConversations;

newChatBtn.addEventListener("click", async () => {
  try {
    const title = `Chat ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
    const res = await authFetch("/conversations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title })
    });
    if (res.ok) {
      const newConv = await res.json();
      currentConvId = newConv.id;
      loadConversations();
      selectConversation(newConv.id, newConv.title);
    }
  } catch (err) {
    console.error("New chat error:", err);
  }
});

async function selectConversation(convId, title) {
  currentConvId = convId;
  chatTitle.textContent = title || "Document Q&A Assistant";
  loadConversations();

  try {
    const res = await authFetch(`/conversations/${convId}`);
    if (res.ok) {
      const data = await res.json();
      renderMessages(data.messages || []);
    }
  } catch (err) {
    console.error("Load history error:", err);
  }
}

window.selectConversation = selectConversation;

function renderMessages(messages) {
  if (!messages || messages.length === 0) {
    chatMessages.innerHTML = `
      <div class="empty-chat">
        <div class="empty-chat-icon">📖</div>
        <h3>Ask Anything About Your Documents</h3>
        <p>Veritas AI uses Self-Healing dense vector retrieval to formulate accurate answers with page citations.</p>
      </div>
    `;
    return;
  }

  chatMessages.innerHTML = messages.map(m => {
    const isUser = m.role === "user";
    return `
      <div class="chat-bubble ${isUser ? 'user' : 'assistant'}">
        <p>${escapeHtml(m.content)}</p>
      </div>
    `;
  }).join("");

  chatMessages.scrollTop = chatMessages.scrollHeight;
}

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const query = chatInput.value.trim();
  if (!query) return;

  if (!currentConvId) {
    await newChatBtn.click();
  }

  // Optimistic message render
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble user";
  bubble.innerHTML = `<p>${escapeHtml(query)}</p>`;
  chatMessages.appendChild(bubble);

  const loaderBubble = document.createElement("div");
  loaderBubble.className = "chat-bubble assistant";
  loaderBubble.innerHTML = `<div class="spinner"></div> <em>Verifying grounding & synthesizing answer...</em>`;
  chatMessages.appendChild(loaderBubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  chatInput.value = "";
  chatInput.disabled = true;

  try {
    const res = await authFetch(`/conversations/${currentConvId}/message`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: query })
    });

    const data = await res.json();
    chatMessages.removeChild(loaderBubble);

    const assistantBubble = document.createElement("div");
    assistantBubble.className = "chat-bubble assistant";
    
    let citationsHtml = "";
    if (data.citations && data.citations.length > 0) {
      citationsHtml = `
        <div class="citations-box">
          <span style="font-size: 10px; color: #A78BFA; font-weight: 600; width: 100%;">SOURCES / CITATIONS:</span>
          ${data.citations.map(c => `<span class="citation-tag">📄 Page ${c.page || '1'}</span>`).join("")}
        </div>
      `;
    }

    assistantBubble.innerHTML = `<p>${escapeHtml(data.answer || "No response.")}</p>${citationsHtml}`;
    chatMessages.appendChild(assistantBubble);
  } catch (err) {
    chatMessages.removeChild(loaderBubble);
    const errBubble = document.createElement("div");
    errBubble.className = "chat-bubble assistant";
    errBubble.innerHTML = `<p style="color: #FCA5A5;">⚠️ ${escapeHtml(err.message)}</p>`;
    chatMessages.appendChild(errBubble);
  } finally {
    chatInput.disabled = false;
    chatInput.focus();
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }
});

async function deleteConversation(convId, e) {
  if (e) e.stopPropagation();
  if (!confirm("Are you sure you want to delete this chat session?")) return;

  try {
    await authFetch(`/conversations/${convId}`, { method: "DELETE" });
    if (currentConvId === convId) currentConvId = null;
    loadConversations();
    renderMessages([]);
  } catch (err) {
    console.error("Delete conversation error:", err);
  }
}

window.deleteConversation = deleteConversation;

// 4. DOCUMENTS CONTROLLER
const docSearchInput = document.getElementById("docSearchInput");
const docStatusFilter = document.getElementById("docStatusFilter");
const documentsTableBody = document.getElementById("documentsTableBody");

docSearchInput.addEventListener("input", () => loadDocuments());
docStatusFilter.addEventListener("change", () => loadDocuments());

async function loadDocuments() {
  try {
    const search = docSearchInput.value.trim();
    const status = docStatusFilter.value;
    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (status) params.append("status", status);

    const res = await authFetch(`/dashboard/recent-documents?${params.toString()}`);
    if (res.ok) {
      const docs = await res.json();
      if (!docs || docs.length === 0) {
        documentsTableBody.innerHTML = `<tr><td colspan="6" class="text-center">No documents found matching filters.</td></tr>`;
      } else {
        documentsTableBody.innerHTML = docs.map(d => `
          <tr>
            <td><strong>📄 ${escapeHtml(d.filename)}</strong></td>
            <td><span class="badge ${d.status === 'processed' ? 'badge-success' : 'badge-warning'}">${d.status}</span></td>
            <td>${d.page_count || 1}</td>
            <td>${formatBytes(d.file_size)}</td>
            <td>${new Date(d.uploaded_at).toLocaleDateString()}</td>
            <td>
              <button class="btn btn-danger btn-sm" onclick="deleteDoc('${d.id}')">Delete</button>
            </td>
          </tr>
        `).join("");
      }
    }
  } catch (err) {
    console.error("Load documents error:", err);
  }
}

window.loadDocuments = loadDocuments;

async function deleteDoc(docId) {
  if (!confirm("Are you sure you want to delete this document?")) return;
  try {
    await authFetch(`/documents/${docId}`, { method: "DELETE" });
    loadDocuments();
    loadDashboard();
  } catch (err) {
    console.error("Delete doc error:", err);
  }
}

window.deleteDoc = deleteDoc;

function escapeHtml(text) {
  if (!text) return "";
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
