const STORAGE_KEY = "face-attendance-camera-lab";

const state = {
  apiBase: "http://localhost:8000",
  kioskToken: "",
  stream: null,
  lastVisitor: null,
};

const elements = {
  apiBase: document.getElementById("apiBase"),
  kioskToken: document.getElementById("kioskToken"),
  connectionState: document.getElementById("connectionState"),
  saveSettings: document.getElementById("saveSettings"),
  video: document.getElementById("video"),
  cameraPlaceholder: document.getElementById("cameraPlaceholder"),
  startCamera: document.getElementById("startCamera"),
  stopCamera: document.getElementById("stopCamera"),
  enrollForm: document.getElementById("enrollForm"),
  enrollButton: document.getElementById("enrollButton"),
  fullName: document.getElementById("fullName"),
  companyName: document.getElementById("companyName"),
  phoneNumber: document.getElementById("phoneNumber"),
  consentGranted: document.getElementById("consentGranted"),
  policyVersion: document.getElementById("policyVersion"),
  identifyButton: document.getElementById("identifyButton"),
  livenessButton: document.getElementById("livenessButton"),
  verifyButton: document.getElementById("verifyButton"),
  checkInButton: document.getElementById("checkInButton"),
  checkOutButton: document.getElementById("checkOutButton"),
  visitorId: document.getElementById("visitorId"),
  verifyVisitorId: document.getElementById("verifyVisitorId"),
  attendanceMethod: document.getElementById("attendanceMethod"),
  output: document.getElementById("output"),
  clearOutput: document.getElementById("clearOutput"),
};

function loadSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    if (typeof saved.apiBase === "string" && saved.apiBase.trim()) {
      state.apiBase = saved.apiBase.trim().replace(/\/+$/, "");
    }
    if (typeof saved.kioskToken === "string") {
      state.kioskToken = saved.kioskToken;
    }
  } catch {
    // Ignore malformed local settings.
  }
  elements.apiBase.value = state.apiBase;
  elements.kioskToken.value = state.kioskToken;
  updateConnectionState();
}

function saveSettings() {
  const apiBase = elements.apiBase.value.trim().replace(/\/+$/, "");
  if (!/^https?:\/\//i.test(apiBase)) {
    log("Settings", { error: "API base URL must start with http:// or https://" });
    return;
  }
  state.apiBase = apiBase;
  state.kioskToken = elements.kioskToken.value.trim();
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({ apiBase: state.apiBase, kioskToken: state.kioskToken })
  );
  updateConnectionState();
  log("Settings saved", { apiBase: state.apiBase, kioskTokenConfigured: Boolean(state.kioskToken) });
}

function updateConnectionState() {
  if (state.apiBase && state.kioskToken) {
    elements.connectionState.textContent = "Configured";
    elements.connectionState.classList.remove("muted");
  } else {
    elements.connectionState.textContent = "Not configured";
    elements.connectionState.classList.add("muted");
  }
}

function log(label, payload) {
  const timestamp = new Date().toLocaleTimeString();
  let rendered;
  try {
    rendered = JSON.stringify(payload, null, 2);
  } catch {
    rendered = String(payload);
  }
  const existing = elements.output.textContent === "Ready." ? "" : `${elements.output.textContent}\n\n`;
  elements.output.textContent = `${existing}[${timestamp}] ${label}\n${rendered}`;
  elements.output.scrollTop = elements.output.scrollHeight;
}

function clearOutput() {
  elements.output.textContent = "Ready.";
}

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    log("Camera error", { error: "This browser does not expose getUserMedia." });
    return;
  }
  stopCamera();
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    });
    state.stream = stream;
    elements.video.srcObject = stream;
    elements.cameraPlaceholder.classList.add("hidden");
    await elements.video.play();
    log("Camera", { status: "started" });
  } catch (error) {
    log("Camera error", { error: error.message || String(error) });
  }
}

function stopCamera() {
  if (state.stream) {
    for (const track of state.stream.getTracks()) {
      track.stop();
    }
  }
  state.stream = null;
  elements.video.srcObject = null;
  elements.cameraPlaceholder.classList.remove("hidden");
}

function captureBlob() {
  return new Promise((resolve, reject) => {
    const video = elements.video;
    if (!state.stream || !video.videoWidth || !video.videoHeight) {
      reject(new Error("Start the camera before capturing an image."));
      return;
    }
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext("2d");
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(
      (blob) => {
        if (blob) {
          resolve(blob);
        } else {
          reject(new Error("Could not capture an image from the camera."));
        }
      },
      "image/jpeg",
      0.92
    );
  });
}

async function apiRequest(path, options = {}) {
  if (!state.apiBase) {
    throw new Error("Set the API base URL first.");
  }
  if (!state.kioskToken) {
    throw new Error("Set the kiosk token first.");
  }
  const headers = { ...(options.headers || {}), "X-Kiosk-Token": state.kioskToken };
  const response = await fetch(`${state.apiBase}${path}`, { ...options, headers });
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json")
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    const error = new Error(
      (body && typeof body === "object" && body.message) || `Request failed with HTTP ${response.status}`
    );
    error.payload = body;
    throw error;
  }
  return body;
}

async function sendImage(path, extraFields = {}) {
  const blob = await captureBlob();
  const form = new FormData();
  form.append("image", blob, "capture.jpg");
  for (const [key, value] of Object.entries(extraFields)) {
    form.append(key, value);
  }
  return apiRequest(path, { method: "POST", body: form });
}

async function enroll(event) {
  event.preventDefault();
  if (!elements.consentGranted.checked) {
    log("Enrollment blocked", { error: "Consent must be checked." });
    return;
  }
  setBusy(elements.enrollButton, true);
  try {
    const response = await sendImage("/api/v1/face/enroll", {
      full_name: elements.fullName.value.trim(),
      company_name: elements.companyName.value.trim(),
      phone_number: elements.phoneNumber.value.trim(),
      consent_granted: "true",
      consent_policy_version: elements.policyVersion.value.trim() || "1.0",
    });
    const visitor = response?.data?.visitor;
    if (visitor?.id) {
      state.lastVisitor = visitor;
      elements.visitorId.value = visitor.id;
    }
    log("Enrollment result", response);
  } catch (error) {
    log("Enrollment error", error.payload || { error: error.message });
  } finally {
    setBusy(elements.enrollButton, false);
  }
}

async function identify() {
  setBusy(elements.identifyButton, true);
  try {
    const response = await sendImage("/api/v1/face/identify");
    const data = response?.data || {};
    if (data.match_status === "MATCHED" && data.visitor?.id) {
      state.lastVisitor = data.visitor;
      elements.visitorId.value = data.visitor.id;
    }
    log("Identification result", response);
  } catch (error) {
    log("Identification error", error.payload || { error: error.message });
  } finally {
    setBusy(elements.identifyButton, false);
  }
}

async function verify() {
  const visitorId = elements.verifyVisitorId.value.trim() || elements.visitorId.value.trim();
  if (!visitorId) {
    log("Verification blocked", { error: "Provide a visitor ID to verify against." });
    return;
  }
  setBusy(elements.verifyButton, true);
  try {
    const response = await sendImage("/api/v1/face/verify", { visitor_id: visitorId });
    log("Verification result", response);
  } catch (error) {
    log("Verification error", error.payload || { error: error.message });
  } finally {
    setBusy(elements.verifyButton, false);
  }
}

async function liveness() {
  setBusy(elements.livenessButton, true);
  try {
    const response = await sendImage("/api/v1/face/liveness");
    log("Liveness result", response);
  } catch (error) {
    log("Liveness error", error.payload || { error: error.message });
  } finally {
    setBusy(elements.livenessButton, false);
  }
}

function idempotencyKey() {
  if (globalThis.crypto?.randomUUID) {
    return crypto.randomUUID();
  }
  return `dev-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

async function attendance(action) {
  const visitorId = elements.visitorId.value.trim();
  if (!visitorId) {
    log("Attendance blocked", { error: "Identify a visitor or paste a visitor ID first." });
    return;
  }
  const button = action === "check-in" ? elements.checkInButton : elements.checkOutButton;
  setBusy(button, true);
  try {
    const response = await apiRequest(`/api/v1/attendance/${action}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey(),
      },
      body: JSON.stringify({
        visitor_id: visitorId,
        method: elements.attendanceMethod.value,
      }),
    });
    log(`Attendance ${action}`, response);
  } catch (error) {
    log(`Attendance ${action} error`, error.payload || { error: error.message });
  } finally {
    setBusy(button, false);
  }
}

function setBusy(button, busy) {
  button.disabled = busy;
}

elements.saveSettings.addEventListener("click", saveSettings);
elements.startCamera.addEventListener("click", startCamera);
elements.stopCamera.addEventListener("click", stopCamera);
elements.enrollForm.addEventListener("submit", enroll);
elements.identifyButton.addEventListener("click", identify);
elements.verifyButton.addEventListener("click", verify);
elements.livenessButton.addEventListener("click", liveness);
elements.checkInButton.addEventListener("click", () => attendance("check-in"));
elements.checkOutButton.addEventListener("click", () => attendance("check-out"));
elements.clearOutput.addEventListener("click", clearOutput);
window.addEventListener("beforeunload", stopCamera);

loadSettings();
