// FastAPI Backend Server Base URL
const API_BASE_URL = "https://ai-enhanced-employee-attendance.onrender.com";

// Active Session Variables
let currentUser = null;
let selectedEmployeeId = null;
let chatHistory = [];
let socket = null;
let reconnectTimer = null;

// DOM Elements
const authSection = document.getElementById("authSection");
const employeePortalSection = document.getElementById("employeePortalSection");
const adminPortalSection = document.getElementById("adminPortalSection");
const userProfileNav = document.getElementById("userProfileNav");

const navUserName = document.getElementById("navUserName");
const navUserRole = document.getElementById("navUserRole");
const logoutBtn = document.getElementById("logoutBtn");

// Auth Tabs
const tabBtnLogin = document.getElementById("tabBtnLogin");
const tabBtnRegister = document.getElementById("tabBtnRegister");
const loginForm = document.getElementById("loginForm");
const registerForm = document.getElementById("registerForm");

// Live Clock
const liveClock = document.getElementById("liveClock");
const liveDate = document.getElementById("liveDate");

// ----------------- DATE & CLOCK SETUP -----------------
function updateLiveClock() {
  const now = new Date();
  
  // Format Time
  let hours = now.getHours();
  let minutes = now.getMinutes();
  let seconds = now.getSeconds();
  hours = hours < 10 ? '0' + hours : hours;
  minutes = minutes < 10 ? '0' + minutes : minutes;
  seconds = seconds < 10 ? '0' + seconds : seconds;
  if (liveClock) liveClock.textContent = `${hours}:${minutes}:${seconds}`;
  
  // Format Date
  const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
  if (liveDate) liveDate.textContent = now.toLocaleDateString('en-US', options);
}
setInterval(updateLiveClock, 1000);
updateLiveClock();

// ----------------- UI TOGGLE UTILITIES -----------------
function showSection(sectionId) {
  authSection.classList.add("hidden");
  employeePortalSection.classList.add("hidden");
  adminPortalSection.classList.add("hidden");
  
  if (sectionId === "auth") {
    authSection.classList.remove("hidden");
    userProfileNav.classList.add("hidden");
    if (socket) {
      socket.close();
      socket = null;
    }
  } else if (sectionId === "employee") {
    employeePortalSection.classList.remove("hidden");
    userProfileNav.classList.remove("hidden");
  } else if (sectionId === "admin") {
    adminPortalSection.classList.remove("hidden");
    userProfileNav.classList.remove("hidden");
  }
}

// Switch between Sign In and Register Tabs
tabBtnLogin.addEventListener("click", () => {
  tabBtnLogin.classList.add("active");
  tabBtnRegister.classList.remove("active");
  loginForm.classList.remove("hidden");
  registerForm.classList.add("hidden");
});

tabBtnRegister.addEventListener("click", () => {
  tabBtnRegister.classList.add("active");
  tabBtnLogin.classList.remove("active");
  registerForm.classList.remove("hidden");
  loginForm.classList.add("hidden");
});

// ----------------- WEBSOCKET CONNECTION MANAGER -----------------
function setupWebSockets(userId, isAdmin) {
  // Clear any existing connections
  if (socket) {
    socket.onclose = null; // Prevent triggers during manual close
    socket.close();
  }
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
  }

  const wsUrl = isAdmin 
    ? `${API_BASE_URL.replace("http", "ws")}/ws/analytics/${userId}`
    : `${API_BASE_URL.replace("http", "ws")}/ws/attendance/${userId}`;

  console.log(`Connecting to WebSocket: ${wsUrl}`);
  socket = new WebSocket(wsUrl);

  const wsStatusDot = document.getElementById("wsStatusDot");
  const wsStatusText = document.getElementById("wsStatusText");

  socket.onopen = () => {
    console.log("WebSocket connection established!");
    if (wsStatusDot) wsStatusDot.className = "status-dot online";
    if (wsStatusText) wsStatusText.textContent = "Connected";
  };

  socket.onclose = () => {
    console.log("WebSocket connection closed. Attempting reconnect...");
    if (wsStatusDot) wsStatusDot.className = "status-dot offline";
    if (wsStatusText) wsStatusText.textContent = "Disconnected";
    
    // Attempt reconnect after 5 seconds
    reconnectTimer = setTimeout(() => {
      setupWebSockets(userId, isAdmin);
    }, 5000);
  };

  socket.onerror = (err) => {
    console.error("WebSocket error:", err);
  };

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handleWebSocketMessage(data, isAdmin);
    } catch (e) {
      console.error("Error parsing WebSocket message:", e);
    }
  };
}

function handleWebSocketMessage(msg, isAdmin) {
  console.log("Received WebSocket Message:", msg);
  
  if (isAdmin) {
    // Admin Handlers
    if (msg.type === "employee_status_update" || msg.type === "attendance_update") {
      const logData = msg.data;
      const statusText = logData.status === "clocked_in" ? "Clocked In" : "Clocked Out";
      const timeStr = new Date(msg.timestamp).toLocaleTimeString();
      logActivityFeed(`<strong>${logData.user_name || 'Employee'}</strong> ${statusText} (ID: ${logData.user_id})`, timeStr);
      
      // Auto-refresh logs and stats
      loadAdminCompanyStatsAndLogs();
      if (selectedEmployeeId === logData.user_id) {
        runPredictiveAnalytics(selectedEmployeeId);
      }
    } else if (msg.type === "alert") {
      showToastAlert(
        `Critical Rule Violation`,
        msg.data.message,
        msg.data.severity || "high"
      );
      loadActiveAlerts();
    }
  } else {
    // Employee Handlers
    if (msg.type === "attendance_update") {
      showToastAlert(
        `Attendance Logged`,
        `Your clock event status: ${msg.data.status.replace("_", " ")}`,
        "low"
      );
      loadEmployeeLogsAndStats();
    }
  }
}

// Prepend live stream activity log
function logActivityFeed(htmlMessage, timeString) {
  const feed = document.getElementById("liveActivityFeed");
  if (!feed) return;
  
  const placeholder = feed.querySelector(".feed-placeholder");
  if (placeholder) placeholder.remove();
  
  const item = document.createElement("div");
  item.className = "feed-item";
  item.innerHTML = `
    <div class="feed-icon">⚡</div>
    <div class="feed-details">
      <p>${htmlMessage}</p>
    </div>
    <div class="feed-time">${timeString}</div>
  `;
  
  feed.insertBefore(item, feed.firstChild);
}

// Show sliding toast alert
function showToastAlert(title, message, severity) {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast-alert ${severity}`;
  
  let icon = "🔔";
  if (severity === "critical") icon = "🚨";
  else if (severity === "high") icon = "⚠️";
  else if (severity === "medium") icon = "⚡";
  else if (severity === "low") icon = "ℹ️";

  toast.innerHTML = `
    <div class="toast-icon">${icon}</div>
    <div class="toast-body">
      <div class="toast-title">${title}</div>
      <div class="toast-desc">${message}</div>
    </div>
    <button type="button" class="toast-close">&times;</button>
  `;

  toast.querySelector(".toast-close").onclick = () => {
    toast.classList.remove("show");
    setTimeout(() => toast.remove(), 400);
  };

  container.appendChild(toast);
  setTimeout(() => toast.classList.add("show"), 100);

  // Remove toast automatically after 7 seconds
  setTimeout(() => {
    if (toast.parentNode) {
      toast.classList.remove("show");
      setTimeout(() => toast.remove(), 400);
    }
  }, 7000);
}

// ----------------- AUTHENTICATION FLOW -----------------
// Handle Register
registerForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  
  const payload = {
    username: document.getElementById("regUsername").value,
    email: document.getElementById("regEmail").value,
    password: document.getElementById("regPassword").value,
    name: document.getElementById("regName").value,
    role: document.getElementById("regRole").value,
    department: document.getElementById("regDept").value
  };
  
  try {
    const res = await fetch(`${API_BASE_URL}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Registration failed");
    
    alert("Registration successful! Please sign in using your credentials.");
    tabBtnLogin.click(); // Toggle back to login
    
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
});

// Handle Login
loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  
  const payload = {
    username: document.getElementById("loginUsername").value,
    password: document.getElementById("loginPassword").value
  };
  
  try {
    const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Login failed");
    
    currentUser = data;
    
    // Update Header
    navUserName.textContent = currentUser.name;
    navUserRole.textContent = currentUser.role === "admin" ? "HR Administrator" : `Employee | ${currentUser.department}`;
    
    // Setup WebSocket
    setupWebSockets(currentUser.id, currentUser.role === "admin");
    
    // Load Portal
    if (currentUser.role === "admin") {
      showSection("admin");
      initAdminDashboard();
    } else {
      showSection("employee");
      initEmployeePortal();
    }
    
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
});

// Handle Logout
logoutBtn.addEventListener("click", () => {
  currentUser = null;
  selectedEmployeeId = null;
  chatHistory = [];
  if (socket) {
    socket.close();
    socket = null;
  }
  showSection("auth");
  loginForm.reset();
  registerForm.reset();
});

// ----------------- EMPLOYEE PORTAL MODULES -----------------
async function initEmployeePortal() {
  document.getElementById("empProfileName").textContent = currentUser.name;
  document.getElementById("empProfileDept").textContent = `${currentUser.department} Department`;
  document.getElementById("empAvatar").textContent = currentUser.name.charAt(0);
  
  // Set default times in clock form
  document.getElementById("clockInTime").value = "09:00";
  document.getElementById("clockOutTime").value = "17:00";
  
  loadEmployeeLogsAndStats();
}

// Mark attendance
document.getElementById("markAttendanceForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  
  const statusVal = document.querySelector('input[name="markStatus"]:checked').value;
  const dateStr = new Date().toISOString().split('T')[0]; // Current date
  
  const payload = {
    user_id: currentUser.id,
    date: dateStr,
    clock_in: document.getElementById("clockInTime").value,
    clock_out: document.getElementById("clockOutTime").value || null,
    status: statusVal
  };
  
  try {
    const res = await fetch(`${API_BASE_URL}/api/attendance/mark`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Marking attendance failed");
    
    alert(`Attendance marked successfully as [${statusVal}]!`);
    loadEmployeeLogsAndStats();
    
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
});

async function loadEmployeeLogsAndStats() {
  try {
    const res = await fetch(`${API_BASE_URL}/api/attendance/reports?user_id=${currentUser.id}`);
    const logs = await res.json();
    if (!res.ok) throw new Error("Could not fetch reports");
    
    const logsBody = document.getElementById("employeeLogsBody");
    logsBody.innerHTML = "";
    
    if (logs.length === 0) {
      logsBody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No records found. Submit your first card!</td></tr>`;
      updateEmployeeStatPanels(0, 0, 0, 0);
      return;
    }
    
    let totalDays = logs.length;
    let absences = 0;
    let lates = 0;
    let presentOrLates = 0;
    
    logs.forEach(log => {
      if (log.status === "Absent") absences++;
      else if (log.status === "Late") {
        lates++;
        presentOrLates++;
      } else presentOrLates++;
      
      const badgeClass = log.status.toLowerCase();
      const cOutText = log.clock_out ? log.clock_out : "-";
      const hoursText = log.working_hours ? `${log.working_hours} hrs` : "-";
      
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${log.date}</td>
        <td>${log.clock_in}</td>
        <td>${cOutText}</td>
        <td><span class="badge ${badgeClass}">${log.status}</span></td>
        <td>${hoursText}</td>
      `;
      logsBody.appendChild(row);
    });
    
    const attendanceRate = (presentOrLates / totalDays) * 100;
    updateEmployeeStatPanels(attendanceRate, totalDays, lates, absences);
    
  } catch (err) {
    console.error("Load employee data error:", err);
  }
}

function updateEmployeeStatPanels(rate, total, lates, absences) {
  document.getElementById("empStatRate").textContent = `${rate.toFixed(1)}%`;
  document.getElementById("empStatDays").textContent = total;
  document.getElementById("empStatLates").textContent = lates;
  document.getElementById("empStatAbsences").textContent = absences;
}

// ----------------- HR ADMINISTRATOR PORTAL MODULES -----------------
async function initAdminDashboard() {
  // Setup tabs routing
  initAdminTabs();
  
  // Dashboard default loads
  loadAdminCompanyStatsAndLogs();
  loadAllEmployeesList();
  
  // Setup manual attendance form date picker default to today
  const today = new Date().toISOString().split('T')[0];
  document.getElementById("adminMarkDate").value = today;
  
  // Setup events for Alert rules and Compliance forms
  setupAlertThresholdListener();
  setupComplianceButtons();
  setupAdvancedSearchListener();
}

// Admin Panel Tabs Controller
function initAdminTabs() {
  const tabBtns = document.querySelectorAll(".admin-tab-btn");
  const tabPanels = document.querySelectorAll(".admin-tab-panel");
  
  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetTab = btn.getAttribute("data-tab");
      
      // Set active button
      tabBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      
      // Show matching panel
      tabPanels.forEach(panel => {
        if (panel.id === targetTab) {
          panel.classList.add("active");
        } else {
          panel.classList.remove("active");
        }
      });
      
      // Load specific tab datasets
      if (targetTab === "adminTrendsTab") {
        loadTrendsData();
      } else if (targetTab === "adminAlertsTab") {
        loadAlertsData();
      } else if (targetTab === "adminComplianceTab") {
        loadComplianceData();
      } else if (targetTab === "adminSearchTab") {
        loadSearchSavedFilters();
      }
    });
  });
}

async function loadAdminCompanyStatsAndLogs() {
  try {
    const res = await fetch(`${API_BASE_URL}/api/attendance/reports`);
    const logs = await res.json();
    if (!res.ok) throw new Error("Could not load reports");
    
    const logsBody = document.getElementById("adminLogsBody");
    logsBody.innerHTML = "";
    
    if (logs.length === 0) {
      logsBody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">No records found. Seed data first!</td></tr>`;
      return;
    }
    
    let totalAbsences = 0;
    let totalLates = 0;
    let totalPresents = 0;
    
    logs.forEach(log => {
      if (log.status === "Absent") totalAbsences++;
      else if (log.status === "Late") {
        totalLates++;
        totalPresents++;
      } else totalPresents++;
      
      const badgeClass = log.status.toLowerCase();
      const cOutText = log.clock_out ? log.clock_out : "-";
      const hoursText = log.working_hours ? `${log.working_hours} hrs` : "-";
      
      const row = document.createElement("tr");
      row.innerHTML = `
        <td style="font-weight: 600;">${log.employee_name}</td>
        <td>${log.department}</td>
        <td>${log.date}</td>
        <td>${log.clock_in}</td>
        <td>${cOutText}</td>
        <td><span class="badge ${badgeClass}">${log.status}</span></td>
        <td style="font-weight: 600;">${hoursText}</td>
      `;
      logsBody.appendChild(row);
    });
    
    // Global stats calculations
    const totalRecords = logs.length;
    const globalAttendanceRate = (totalPresents / totalRecords) * 100;
    
    document.getElementById("adminCompanyRate").textContent = `${globalAttendanceRate.toFixed(1)}%`;
    document.getElementById("adminTotalAbsences").textContent = totalAbsences;
    document.getElementById("adminTotalLates").textContent = totalLates;
    
  } catch (err) {
    console.error("Admin stats/logs error:", err);
  }
}

// Global Refresh button
document.getElementById("adminGlobalRefreshBtn").addEventListener("click", () => {
  loadAdminCompanyStatsAndLogs();
  loadAllEmployeesList();
  
  // Refresh active tab
  const activeTabBtn = document.querySelector(".admin-tab-btn.active");
  if (activeTabBtn) {
    activeTabBtn.click();
  }
});

// Global Search Filtering
document.getElementById("adminGlobalSearch").addEventListener("input", (e) => {
  const searchTerm = e.target.value.toLowerCase();
  
  // Filter Employee Sidebar
  const empItems = document.querySelectorAll(".employee-select-item");
  empItems.forEach(item => {
    const text = item.textContent.toLowerCase();
    if (text.includes(searchTerm)) {
      item.style.display = "flex";
    } else {
      item.style.display = "none";
    }
  });
  
  // Filter Master Logs
  const logRows = document.querySelectorAll("#adminLogsBody tr");
  logRows.forEach(row => {
    if (row.cells.length === 1) return;
    const text = row.textContent.toLowerCase();
    if (text.includes(searchTerm)) {
      row.style.display = ""; 
    } else {
      row.style.display = "none";
    }
  });
});

// Load employee list for selectors and lists
async function loadAllEmployeesList() {
  try {
    const res = await fetch(`${API_BASE_URL}/api/attendance/employees`);
    const employees = await res.json();
    if (!res.ok) throw new Error("Could not load employee details");
    
    // 1. Selector in Manual marking form
    const selectEl = document.getElementById("adminSelectEmployee");
    selectEl.innerHTML = "";
    
    // 2. Selectors in Compliance module
    const complianceSelector = document.getElementById("complianceEmployeeSelector");
    if (complianceSelector) complianceSelector.innerHTML = "";
    
    // Domain Selection for New Employees
    const newDeptSelect = document.getElementById("newEmpDeptSelect");
    newDeptSelect.innerHTML = `<option value="" disabled selected>Select a domain...</option>`;
    const uniqueDomains = new Set();
    
    employees.forEach(emp => {
      uniqueDomains.add(emp.department);
      
      const option = document.createElement("option");
      option.value = emp.id;
      option.textContent = `${emp.name} (${emp.department})`;
      selectEl.appendChild(option);
      
      if (complianceSelector) {
        const optionCopy = option.cloneNode(true);
        complianceSelector.appendChild(optionCopy);
      }
    });
    
    uniqueDomains.forEach(domain => {
      const option = document.createElement("option");
      option.value = domain;
      option.textContent = domain;
      newDeptSelect.appendChild(option);
    });
    const addDomainOpt = document.createElement("option");
    addDomainOpt.value = "--NEW--";
    addDomainOpt.textContent = "+ Add New Domain";
    newDeptSelect.appendChild(addDomainOpt);
    
    // 3. Interactive grid selector in sidebar
    const listEl = document.getElementById("adminEmployeeList");
    listEl.innerHTML = "";
    
    document.getElementById("adminTotalEmployees").textContent = employees.length;
    
    employees.forEach((emp, idx) => {
      const initials = emp.name.split(" ").map(n => n.charAt(0)).join("");
      
      const item = document.createElement("div");
      item.className = "employee-select-item";
      item.setAttribute("data-id", emp.id);
      
      item.innerHTML = `
        <div class="avatar-small">${initials}</div>
        <div class="emp-name-dept">
          <h4>${emp.name}</h4>
          <p>${emp.department}</p>
        </div>
      `;
      
      item.addEventListener("click", () => {
        document.querySelectorAll(".employee-select-item").forEach(el => el.classList.remove("active"));
        item.classList.add("active");
        
        selectedEmployeeId = emp.id;
        runPredictiveAnalytics(emp.id);
      });
      
      listEl.appendChild(item);
      
      // Auto select first employee in list initially
      if (idx === 0) {
        item.click();
      }
    });
    
  } catch (err) {
    console.error("Load employees list error:", err);
  }
}

// Admin manual mark form submit
document.getElementById("adminManualMarkForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  
  const payload = {
    user_id: parseInt(document.getElementById("adminSelectEmployee").value),
    date: document.getElementById("adminMarkDate").value,
    status: document.getElementById("adminMarkStatus").value,
    clock_in: document.getElementById("adminMarkClockIn").value,
    clock_out: document.getElementById("adminMarkClockOut").value || null
  };
  
  try {
    const res = await fetch(`${API_BASE_URL}/api/attendance/mark`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Manual mark failed");
    
    alert("Employee record saved successfully!");
    loadAdminCompanyStatsAndLogs();
    
    // Refresh current selected employee metrics if applicable
    if (selectedEmployeeId === payload.user_id) {
      runPredictiveAnalytics(selectedEmployeeId);
    }
    
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
});

// Handle Domain select change
document.getElementById("newEmpDeptSelect").addEventListener("change", (e) => {
  const newDomainGroup = document.getElementById("newDomainGroup");
  const newDomainInput = document.getElementById("newEmpNewDept");
  if (e.target.value === "--NEW--") {
    newDomainGroup.classList.remove("hidden");
    newDomainInput.required = true;
  } else {
    newDomainGroup.classList.add("hidden");
    newDomainInput.required = false;
    newDomainInput.value = "";
  }
});

// Admin Add Employee / Domain Form
document.getElementById("adminAddEmployeeForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  
  let domain = document.getElementById("newEmpDeptSelect").value;
  if (domain === "--NEW--") {
    domain = document.getElementById("newEmpNewDept").value;
  }
  
  const payload = {
    username: document.getElementById("newEmpUsername").value,
    email: `${document.getElementById("newEmpUsername").value}@company.com`,
    password: document.getElementById("newEmpPassword").value,
    name: document.getElementById("newEmpName").value,
    role: "employee",
    department: domain
  };
  
  try {
    const res = await fetch(`${API_BASE_URL}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Adding entry failed");
    
    alert("New Employee & Domain added successfully!");
    document.getElementById("adminAddEmployeeForm").reset();
    document.getElementById("newDomainGroup").classList.add("hidden");
    
    loadAllEmployeesList();
    
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
});

// ----------------- PREDICTIVE ANALYTICS & GENAI INSIGHTS -----------------
async function runPredictiveAnalytics(userId) {
  const mlLoading = document.getElementById("mlLoading");
  const mlResultContent = document.getElementById("mlResultContent");
  const aiLoading = document.getElementById("aiLoading");
  const aiResultContent = document.getElementById("aiResultContent");
  
  mlLoading.classList.remove("hidden");
  mlResultContent.classList.add("hidden");
  aiLoading.classList.remove("hidden");
  aiResultContent.classList.add("hidden");
  
  document.getElementById("chatInputText").disabled = true;
  document.getElementById("chatSendBtn").disabled = true;
  document.getElementById("clearChatBtn").disabled = true;
  
  try {
    // 1. Fetch ML predictive scoring
    const mlRes = await fetch(`${API_BASE_URL}/api/analytics/predict/${userId}`);
    const mlData = await mlRes.json();
    if (!mlRes.ok) throw new Error("ML prediction failed");
    
    // Update ML Card Values
    document.getElementById("mlEmpName").textContent = mlData.employee_name;
    const catBadge = document.getElementById("mlCategoryBadge");
    catBadge.textContent = mlData.prediction;
    
    catBadge.className = "prediction-category"; // Reset
    if (mlData.prediction.includes("Regular")) {
      catBadge.classList.add("regular");
    } else if (mlData.prediction.includes("Irregular")) {
      catBadge.classList.add("irregular");
    } else {
      catBadge.classList.add("at-risk");
    }
    
    document.getElementById("mlConfidenceText").textContent = `${mlData.confidence}%`;
    document.getElementById("mlConfidenceBar").style.width = `${mlData.confidence}%`;
    document.getElementById("mlDescriptionText").textContent = mlData.description;
    
    // Update ML features values list
    document.getElementById("featRate").textContent = `${(mlData.features.Attendance_Rate * 100).toFixed(1)}%`;
    document.getElementById("featAbsences").textContent = `${mlData.features.Absences} days`;
    document.getElementById("featLates").textContent = `${mlData.features.Late_Arrivals} arrivals`;
    document.getElementById("featHours").textContent = `${mlData.features.Avg_Working_Hours} hrs/day`;
    document.getElementById("featTrend").textContent = `${mlData.features.Mon_Fri_Late_Trend} / 10`;
    
    mlLoading.classList.add("hidden");
    mlResultContent.classList.remove("hidden");
    
    // 2. Fetch Google Gemini Insights
    const aiRes = await fetch(`${API_BASE_URL}/api/analytics/insights/${userId}`);
    const aiData = await aiRes.json();
    if (!aiRes.ok) throw new Error("AI insights generation failed");
    
    const insightsBox = document.getElementById("aiInsightsBox");
    insightsBox.innerHTML = `
      <p style="margin-bottom:8px; font-weight:600; color:var(--accent-cyan); font-size:12px; text-transform:uppercase; letter-spacing:0.05em;">AI Summary & Recommendation:</p>
      <p>${aiData.ai_insights}</p>
    `;
    
    // 3. Fetch persistent multi-turn chat logs history from database
    const chatHistRes = await fetch(`${API_BASE_URL}/api/chat/history/${userId}`);
    const chatHistData = await chatHistRes.json();
    
    const chatBox = document.getElementById("chatHistoryBox");
    chatBox.innerHTML = "";
    chatHistory = [];
    
    // Prepend system welcome message
    const welcomeBubble = document.createElement("div");
    welcomeBubble.className = "chat-bubble ai";
    welcomeBubble.innerHTML = `Hello! I have loaded all attendance logs and predictive analytics for <strong>${mlData.employee_name}</strong>. Feel free to ask me questions like <em>"What advice do you have?"</em> or <em>"Are they late often?"</em>.`;
    chatBox.appendChild(welcomeBubble);
    
    if (chatHistRes.ok && chatHistData.messages && chatHistData.messages.length > 0) {
      chatHistData.messages.forEach(msg => {
        const bubble = document.createElement("div");
        bubble.className = `chat-bubble ${msg.sender === "user" ? "user" : "ai"}`;
        bubble.textContent = msg.message;
        chatBox.appendChild(bubble);
        
        chatHistory.push({ role: msg.sender === "user" ? "user" : "assistant", content: msg.message });
      });
      document.getElementById("clearChatBtn").disabled = false;
    }
    
    chatBox.scrollTop = chatBox.scrollHeight;
    
    // Enable Chat inputs
    document.getElementById("chatInputText").value = "";
    document.getElementById("chatInputText").disabled = false;
    document.getElementById("chatSendBtn").disabled = false;
    
    aiLoading.classList.add("hidden");
    aiResultContent.classList.remove("hidden");
    
    // Dynamic refresh of secondary tabs if open
    const activeTab = document.querySelector(".admin-tab-btn.active").getAttribute("data-tab");
    if (activeTab === "adminTrendsTab") {
      loadTrendsData();
    } else if (activeTab === "adminComplianceTab") {
      loadComplianceData();
    }
    
  } catch (err) {
    console.error("Predictive flow error:", err);
    alert("Analytics load error. Ensure your FastAPI Backend is running at http://127.0.0.1:5000");
  }
}

// ----------------- HR AI CHAT ASSISTANT PANEL -----------------
async function submitChatQuestion() {
  const inputEl = document.getElementById("chatInputText");
  const question = inputEl.value.trim();
  if (!question || !selectedEmployeeId) return;
  
  inputEl.value = "";
  const chatBox = document.getElementById("chatHistoryBox");
  
  // Append User message bubble
  const userBubble = document.createElement("div");
  userBubble.className = "chat-bubble user";
  userBubble.textContent = question;
  chatBox.appendChild(userBubble);
  chatBox.scrollTop = chatBox.scrollHeight;
  
  chatHistory.push({ role: "user", content: question });
  
  // Append typing placeholder
  const aiBubble = document.createElement("div");
  aiBubble.className = "chat-bubble ai";
  aiBubble.innerHTML = `<span style="font-style:italic; color:var(--text-muted);">Analyzing database metrics...</span>`;
  chatBox.appendChild(aiBubble);
  chatBox.scrollTop = chatBox.scrollHeight;
  
  const payload = {
    user_id: selectedEmployeeId,
    question: question,
    history: chatHistory
  };
  
  try {
    const res = await fetch(`${API_BASE_URL}/api/chat/send`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Chat error");
    
    // Replace Typing placeholder with response
    aiBubble.innerHTML = data.response;
    chatBox.scrollTop = chatBox.scrollHeight;
    
    // Update local chat history array
    chatHistory.push({ role: "assistant", content: data.response });
    document.getElementById("clearChatBtn").disabled = false;
    
  } catch (err) {
    aiBubble.innerHTML = `<span style="color:var(--danger);">Error: Could not retrieve answer from AI.</span>`;
    console.error("AI Chat error:", err);
  }
}

// Trigger Chat Submit
document.getElementById("chatSendBtn").addEventListener("click", submitChatQuestion);
document.getElementById("chatInputText").addEventListener("keypress", (e) => {
  if (e.key === "Enter") {
    submitChatQuestion();
  }
});

// Clear Chat session in database
document.getElementById("clearChatBtn").addEventListener("click", async () => {
  if (!selectedEmployeeId) return;
  if (!confirm("Are you sure you want to clear chat history logs for this employee?")) return;
  
  try {
    const res = await fetch(`${API_BASE_URL}/api/chat/clear/${selectedEmployeeId}`, {
      method: "DELETE"
    });
    
    if (res.ok) {
      alert("Chat history logs cleared!");
      const chatBox = document.getElementById("chatHistoryBox");
      chatBox.innerHTML = `
        <div class="chat-bubble ai">
          Hello! Chat history has been cleared. Ask me any new questions about this employee.
        </div>
      `;
      chatHistory = [];
      document.getElementById("clearChatBtn").disabled = true;
    }
  } catch (err) {
    console.error("Clear chat error:", err);
  }
});

// ----------------- TAB 2: TREND ANALYTICS -----------------
async function loadTrendsData() {
  const deptContainer = document.getElementById("deptComparisonContainer");
  const forecastContainer = document.getElementById("trendForecastContent");
  const seasonalContainer = document.getElementById("seasonalPatternsContent");
  
  // 1. Load Department Comparisons summary
  try {
    const deptRes = await fetch(`${API_BASE_URL}/api/analytics/departments`);
    const deptData = await deptRes.json();
    
    if (deptRes.ok && deptData.departments) {
      deptContainer.innerHTML = "";
      deptData.departments.forEach(dept => {
        const card = document.createElement("div");
        card.className = "dept-card";
        card.innerHTML = `
          <div class="dept-name">${dept.department}</div>
          <div class="dept-metric-row">
            <span>Present Rate</span>
            <span>${(dept.attendance_rate || 0).toFixed(1)}%</span>
          </div>
          <div class="dept-metric-row">
            <span>Avg Work Hours</span>
            <span>${(dept.avg_working_hours || 0).toFixed(1)} hrs</span>
          </div>
          <div class="dept-metric-row">
            <span>Active Headcount</span>
            <span>${dept.total_employees || 0}</span>
          </div>
        `;
        deptContainer.appendChild(card);
      });
    } else {
      deptContainer.innerHTML = `<div style="color:var(--text-muted); text-align:center;">Failed to retrieve department data.</div>`;
    }
  } catch (e) {
    console.error(e);
  }
  
  // 2. Load Selected Employee Forecasting
  if (!selectedEmployeeId) {
    forecastContainer.innerHTML = `<div class="forecast-placeholder">Select an employee from the Dashboard list to check forecasts.</div>`;
    seasonalContainer.innerHTML = `<div class="forecast-placeholder">Select an employee from the Dashboard list to check day-of-week lateness.</div>`;
    return;
  }
  
  try {
    forecastContainer.innerHTML = `<div class="loading-container"><div class="loader-spinner"></div>Analyzing forecasts...</div>`;
    const trendsRes = await fetch(`${API_BASE_URL}/api/analytics/trends/${selectedEmployeeId}`);
    const trends = await trendsRes.json();
    
    if (trendsRes.ok) {
      const attRate = trends.monthly_trend ? trends.monthly_trend.attendance_rate : 0;
      const forecast7 = trends.forecast_7days ? trends.forecast_7days.expected_attendance_rate : 0;
      const direction = trends.trend_direction ? (trends.trend_direction.direction || 'stable') : 'stable';
      const confidence = trends.trend_direction ? (trends.trend_direction.confidence || 0) : 0;
      const change = trends.trend_direction ? (trends.trend_direction.weekly_vs_monthly_change || 0) : 0;
      
      forecastContainer.innerHTML = `
        <div class="forecast-card">
          <div class="forecast-metric-container">
            <div class="forecast-metric-card">
              <div class="forecast-val">${attRate.toFixed(1)}%</div>
              <div class="forecast-label">Attendance Rate (30d)</div>
            </div>
            <div class="forecast-metric-card">
              <div class="forecast-val">${forecast7.toFixed(1)}%</div>
              <div class="forecast-label">7-Day Forecast</div>
            </div>
          </div>
          <div class="forecast-desc">
            <strong>Trend Direction:</strong> ${direction.toUpperCase().replace('_', ' ')} (${confidence}% Confidence)<br>
            <strong>Recent Velocity:</strong> ${change >= 0 ? '+' : ''}${change.toFixed(1)}% (Weekly vs Monthly attendance rate variance).
          </div>
        </div>
      `;
    } else {
      forecastContainer.innerHTML = `<div style="color:var(--text-muted); text-align:center;">Error retrieving forecast trends.</div>`;
    }
  } catch (e) {
    console.error(e);
  }
  
  // 3. Load Seasonal Patterns
  try {
    seasonalContainer.innerHTML = `<div class="loading-container"><div class="loader-spinner"></div>Analyzing seasonal trends...</div>`;
    const seasonalRes = await fetch(`${API_BASE_URL}/api/analytics/seasonal/${selectedEmployeeId}`);
    const seasonal = await seasonalRes.json();
    
    if (seasonalRes.ok) {
      seasonalContainer.innerHTML = "";
      
      const dow = seasonal.day_of_week_lateness || {};
      const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];
      
      days.forEach(day => {
        const val = dow[day] || 0;
        const row = document.createElement("div");
        row.className = "seasonal-grid-row";
        row.innerHTML = `
          <span class="seasonal-day">${day}</span>
          <span class="seasonal-value">${val} Late instance(s)</span>
        `;
        seasonalContainer.appendChild(row);
      });
      
      if (seasonal.seasonal_anomalies && seasonal.seasonal_anomalies.length > 0) {
        const warning = document.createElement("div");
        warning.className = "forecast-desc";
        warning.style.borderColor = "var(--warning)";
        warning.style.marginTop = "12px";
        warning.innerHTML = `<strong>Seasonal Alerts:</strong> ${seasonal.seasonal_anomalies.join(", ")}`;
        seasonalContainer.appendChild(warning);
      }
    } else {
      seasonalContainer.innerHTML = `<div style="color:var(--text-muted); text-align:center;">Error loading seasonal trends.</div>`;
    }
  } catch (e) {
    console.error(e);
  }
}

// ----------------- TAB 3: ADVANCED SEARCH -----------------
function setupAdvancedSearchListener() {
  const form = document.getElementById("advSearchForm");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    executeAdvancedSearch();
  });
}

async function executeAdvancedSearch() {
  const query = document.getElementById("advSearchQuery").value.trim();
  const department = document.getElementById("advSearchDept").value;
  const role = document.getElementById("advSearchRole").value;
  const status = document.getElementById("advSearchStatus").value;
  const dateFrom = document.getElementById("advSearchDateFrom").value;
  const dateTo = document.getElementById("advSearchDateTo").value;
  const saveFilterName = document.getElementById("advSearchSaveName").value.trim();
  
  const payload = {
    query: query || null,
    department: department || null,
    role: role || null,
    status: status || null,
    date_from: dateFrom || null,
    date_to: dateTo || null,
    save_filter_name: saveFilterName || null,
    user_id: currentUser.id
  };
  
  const resultsBody = document.getElementById("advSearchResultsBody");
  resultsBody.innerHTML = `<tr><td colspan="7" style="text-align:center;"><div class="loader-spinner"></div>Running database query...</td></tr>`;
  
  try {
    const res = await fetch(`${API_BASE_URL}/api/search/advanced`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    
    const data = await res.json();
    if (!res.ok) throw new Error("Search query failure");
    
    resultsBody.innerHTML = "";
    if (data.length === 0) {
      resultsBody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-muted);">No employees match the criteria.</td></tr>`;
      return;
    }
    
    data.forEach(item => {
      const row = document.createElement("tr");
      const riskClass = item.risk_level.toLowerCase();
      row.innerHTML = `
        <td style="font-weight:600;">${item.name}</td>
        <td>${item.department}</td>
        <td>${item.role}</td>
        <td>${item.email}</td>
        <td>${item.prediction}</td>
        <td><span class="alert-badge ${riskClass}">${item.risk_level}</span></td>
        <td style="font-weight:600;">${item.risk_score.toFixed(1)}%</td>
      `;
      resultsBody.appendChild(row);
    });
    
    // Clear save name field if populated
    document.getElementById("advSearchSaveName").value = "";
    
    // Refresh filters list
    loadSearchSavedFilters();
    
  } catch (err) {
    resultsBody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--danger);">Error running search filters.</td></tr>`;
  }
}

// Load Saved Filters
async function loadSearchSavedFilters() {
  const container = document.getElementById("savedFiltersList");
  try {
    const res = await fetch(`${API_BASE_URL}/api/search/filters/${currentUser.id}`);
    const filters = await res.json();
    
    if (res.ok && filters.length > 0) {
      container.innerHTML = "";
      filters.forEach(f => {
        const pill = document.createElement("div");
        pill.className = "filter-pill";
        pill.innerHTML = `
          <span>${f.name}</span>
          <button type="button" class="filter-delete-btn" data-id="${f.id}">&times;</button>
        `;
        
        // Load filter on click
        pill.addEventListener("click", (e) => {
          if (e.target.classList.contains("filter-delete-btn")) return;
          loadSavedFilterCriteria(f.criteria);
        });
        
        // Delete filter on close click
        pill.querySelector(".filter-delete-btn").addEventListener("click", async (e) => {
          e.stopPropagation();
          if (confirm(`Delete saved filter "${f.name}"?`)) {
            const delRes = await fetch(`${API_BASE_URL}/api/search/filters/${f.id}`, { method: "DELETE" });
            if (delRes.ok) {
              loadSearchSavedFilters();
            }
          }
        });
        
        container.appendChild(pill);
      });
    } else {
      container.innerHTML = `<div style="font-style:italic; color:var(--text-muted); font-size:13px;">No saved filters.</div>`;
    }
  } catch (e) {
    console.error(e);
  }
}

function loadSavedFilterCriteria(criteria) {
  document.getElementById("advSearchQuery").value = criteria.query || "";
  document.getElementById("advSearchDept").value = criteria.department || "";
  document.getElementById("advSearchRole").value = criteria.role || "";
  document.getElementById("advSearchStatus").value = criteria.status || "";
  document.getElementById("advSearchDateFrom").value = criteria.date_from || "";
  document.getElementById("advSearchDateTo").value = criteria.date_to || "";
  
  executeAdvancedSearch();
}

// Export search results to CSV
document.getElementById("exportCsvBtn").addEventListener("click", async () => {
  const query = document.getElementById("advSearchQuery").value.trim();
  const department = document.getElementById("advSearchDept").value;
  const role = document.getElementById("advSearchRole").value;
  const status = document.getElementById("advSearchStatus").value;
  const dateFrom = document.getElementById("advSearchDateFrom").value;
  const dateTo = document.getElementById("advSearchDateTo").value;
  
  const payload = {
    query: query || null,
    department: department || null,
    role: role || null,
    status: status || null,
    date_from: dateFrom || null,
    date_to: dateTo || null,
    user_id: currentUser.id
  };
  
  try {
    const res = await fetch(`${API_BASE_URL}/api/search/advanced/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    
    if (res.ok) {
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `advanced_search_results_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } else {
      alert("Failed to export search results.");
    }
  } catch (err) {
    console.error("Export CSV Error:", err);
  }
});

// ----------------- TAB 4: SMART ALERTING -----------------
async function loadAlertsData() {
  loadActiveAlerts();
  
  // Load Threshold settings
  try {
    const res = await fetch(`${API_BASE_URL}/api/alerts/thresholds`);
    const thresholds = await res.json();
    
    if (res.ok) {
      document.getElementById("threshLate").value = thresholds.late_minutes_threshold;
      document.getElementById("threshRisk").value = thresholds.risk_score_threshold;
      document.getElementById("threshAnomaly").value = thresholds.anomaly_score_threshold;
      document.getElementById("threshEscalation").value = thresholds.escalation_occurrences;
    }
  } catch (e) {
    console.error(e);
  }
}

async function loadActiveAlerts() {
  const container = document.getElementById("activeAlertsList");
  const alertBadge = document.getElementById("alertBadgeCount");
  
  try {
    const res = await fetch(`${API_BASE_URL}/api/alerts/active`);
    const alerts = await res.json();
    
    if (res.ok) {
      if (alerts.length === 0) {
        container.innerHTML = `<div style="color:var(--text-muted); font-style:italic; text-align:center; padding:40px 0;">No active alerts. System is green!</div>`;
        if (alertBadge) alertBadge.classList.add("hidden");
        return;
      }
      
      // Update badge count
      if (alertBadge) {
        alertBadge.textContent = alerts.length;
        alertBadge.classList.remove("hidden");
      }
      
      container.innerHTML = "";
      alerts.forEach(al => {
        const card = document.createElement("div");
        const sevClass = al.severity.toLowerCase();
        card.className = `alert-card ${sevClass}`;
        
        card.innerHTML = `
          <div class="alert-details">
            <div class="alert-header-row">
              <h4>${al.employee_name}</h4>
              <span class="alert-badge ${sevClass}">${al.severity}</span>
              <span style="font-size:11px; color:var(--text-muted);">Occurrences: ${al.occurrences}</span>
            </div>
            <div class="alert-body-text">${al.message}</div>
          </div>
          <button type="button" class="ack-btn" data-id="${al.id}">Acknowledge</button>
        `;
        
        card.querySelector(".ack-btn").onclick = async () => {
          const ackRes = await fetch(`${API_BASE_URL}/api/alerts/${al.id}/acknowledge`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ admin_id: currentUser.id })
          });
          if (ackRes.ok) {
            loadActiveAlerts();
          } else {
            alert("Could not acknowledge alert.");
          }
        };
        
        container.appendChild(card);
      });
    }
  } catch (e) {
    console.error(e);
  }
}

function setupAlertThresholdListener() {
  const form = document.getElementById("alertThresholdsForm");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    
    const payload = {
      late_minutes_threshold: parseInt(document.getElementById("threshLate").value),
      risk_score_threshold: parseFloat(document.getElementById("threshRisk").value),
      anomaly_score_threshold: parseFloat(document.getElementById("threshAnomaly").value),
      escalation_occurrences: parseInt(document.getElementById("threshEscalation").value)
    };
    
    try {
      const res = await fetch(`${API_BASE_URL}/api/alerts/thresholds?admin_id=${currentUser.id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      
      if (res.ok) {
        alert("Alert thresholds rules updated successfully!");
        loadAlertsData();
      } else {
        throw new Error();
      }
    } catch (e) {
      alert("Failed to update thresholds.");
    }
  });
}

// ----------------- TAB 5: GDPR & COMPLIANCE -----------------
async function loadComplianceData() {
  // Populate the Selector
  const selector = document.getElementById("complianceEmployeeSelector");
  const selectedEmpId = parseInt(selector.value);
  if (selectedEmpId) {
    loadComplianceAuditLogs(selectedEmpId);
  }
}

async function loadComplianceAuditLogs(employeeId) {
  const body = document.getElementById("complianceAuditBody");
  body.innerHTML = `<tr><td colspan="4" style="text-align:center;"><div class="loader-spinner"></div>Retrieving audit records...</td></tr>`;
  
  try {
    const res = await fetch(`${API_BASE_URL}/api/compliance/audit-trail/${employeeId}?actor_id=${currentUser.id}`);
    const logs = await res.json();
    
    if (res.ok) {
      body.innerHTML = "";
      if (logs.length === 0) {
        body.innerHTML = `<tr><td colspan="4" style="text-align:center; color:var(--text-muted);">No compliance logs recorded for this employee profile.</td></tr>`;
        return;
      }
      
      logs.forEach(log => {
        const row = document.createElement("tr");
        row.innerHTML = `
          <td>Actor ID: ${log.actor_id}</td>
          <td style="font-weight:600; color:var(--accent-cyan);">${log.action}</td>
          <td>${log.resource}</td>
          <td>${new Date(log.timestamp).toLocaleString()}</td>
        `;
        body.appendChild(row);
      });
    } else {
      body.innerHTML = `<tr><td colspan="4" style="text-align:center; color:var(--danger);">Error loading compliance logs.</td></tr>`;
    }
  } catch (e) {
    console.error(e);
  }
}

function setupComplianceButtons() {
  const selector = document.getElementById("complianceEmployeeSelector");
  
  // Selector Change Event
  selector.addEventListener("change", () => {
    const val = parseInt(selector.value);
    if (val) {
      loadComplianceAuditLogs(val);
    }
  });
  
  // Export Data portability
  document.getElementById("exportComplianceBtn").onclick = async () => {
    const val = parseInt(selector.value);
    if (!val) return;
    
    try {
      const res = await fetch(`${API_BASE_URL}/api/compliance/export/${val}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ actor_id: currentUser.id })
      });
      
      if (res.ok) {
        const data = await res.json();
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `employee_${val}_gdpr_data_export.json`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        
        // Reload audits logs
        loadComplianceAuditLogs(val);
      } else {
        alert("Failed to export compliance archive.");
      }
    } catch (e) {
      console.error(e);
    }
  };
  
  // Delete Employee (Right to Forgotten)
  document.getElementById("deleteComplianceBtn").onclick = async () => {
    const val = parseInt(selector.value);
    if (!val) return;
    
    const doubleConfirm = confirm("WARNING: This will permanently delete this employee profile, all attendance records, all alert logs, and all predictions history.\n\nAre you sure you want to permanently execute this erasure?");
    if (!doubleConfirm) return;
    
    try {
      const res = await fetch(`${API_BASE_URL}/api/compliance/delete/${val}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ actor_id: currentUser.id })
      });
      
      const data = await res.json();
      if (res.ok) {
        alert(data.message || "Employee erased successfully.");
        // Reload selector and list
        loadAllEmployeesList();
      } else {
        alert(data.detail || "Deletion failed.");
      }
    } catch (e) {
      console.error(e);
    }
  };
  
  // Cleanup Logs
  document.getElementById("cleanupAuditBtn").onclick = async () => {
    const years = parseInt(document.getElementById("complianceRetentionYears").value);
    if (!years) return;
    
    try {
      const res = await fetch(`${API_BASE_URL}/api/compliance/audit-trail/cleanup?actor_id=${currentUser.id}&retention_years=${years}`, {
        method: "POST"
      });
      const data = await res.json();
      if (res.ok) {
        alert(`Clean up successful! Deleted ${data.deleted_count} logs older than ${years} years.`);
      }
    } catch (e) {
      console.error(e);
    }
  };
}
