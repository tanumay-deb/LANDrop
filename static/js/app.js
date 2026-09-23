/**
 * LANDrop - Web Application Client Script
 * Handles Safe List browsing, drag & drop auto-save uploads,
 * real-time SSE synchronization, clipboard sync, and media previews.
 */

// State
let currentFolderId = "";
let currentSubpath = "";
let safeItemsCache = [];
let cachedSafeFolders = [];
let serverInfo = null;

// DOM Elements
const hostNameDisplay = document.getElementById("hostNameDisplay");
const selectSafeFolder = document.getElementById("selectSafeFolder");
const safeFilesContainer = document.getElementById("safeFilesContainer");
const breadcrumbBar = document.getElementById("breadcrumbBar");
const btnSafeBack = document.getElementById("btnSafeBack");
const safeBackBtnLabel = document.getElementById("safeBackBtnLabel");
const safeSearchInput = document.getElementById("safeSearchInput");
const btnDownloadFolderZip = document.getElementById("btnDownloadFolderZip");
const btnRefreshSafe = document.getElementById("btnRefreshSafe");
const badgeSafeCount = document.getElementById("badgeSafeCount");

// Upload DOM Elements
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const folderInput = document.getElementById("folderInput");
const btnSelectFiles = document.getElementById("btnSelectFiles");
const btnSelectFolder = document.getElementById("btnSelectFolder");
const uploadProgressCard = document.getElementById("uploadProgressCard");
const progressFileName = document.getElementById("progressFileName");
const progressSpeed = document.getElementById("progressSpeed");
const progressPct = document.getElementById("progressPct");
const progressBarFill = document.getElementById("progressBarFill");
const progressTransferred = document.getElementById("progressTransferred");
const progressEta = document.getElementById("progressEta");
const sentList = document.getElementById("sentList");

// Received DOM Elements
const receivedFilesContainer = document.getElementById("receivedFilesContainer");
const receivedPathDesc = document.getElementById("receivedPathDesc");
const btnRefreshReceived = document.getElementById("btnRefreshReceived");

// Clipboard DOM Elements
const clipboardTextarea = document.getElementById("clipboardTextarea");
const btnSendClipboard = document.getElementById("btnSendClipboard");
const btnCopyClipboard = document.getElementById("btnCopyClipboard");
const clipboardUpdatedTime = document.getElementById("clipboardUpdatedTime");

// Modals DOM Elements
const previewModal = document.getElementById("previewModal");
const previewModalTitle = document.getElementById("previewModalTitle");
const previewModalBody = document.getElementById("previewModalBody");
const btnClosePreview = document.getElementById("btnClosePreview");
const btnModalDownload = document.getElementById("btnModalDownload");

const qrModal = document.getElementById("qrModal");
const btnQrModal = document.getElementById("btnQrModal");
const btnCloseQr = document.getElementById("btnCloseQr");
const qrUrlText = document.getElementById("qrUrlText");

// Theme
const btnThemeToggle = document.getElementById("btnThemeToggle");

// SVG Icons mapping
const categoryIcons = {
  folder: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>`,
  image: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>`,
  video: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="23 7 16 12 23 17 23 7"></polygon><rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect></svg>`,
  audio: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18V5l12-2v13"></path><circle cx="6" cy="18" r="3"></circle><circle cx="18" cy="16" r="3"></circle></svg>`,
  document: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>`,
  archive: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="21 8 21 21 3 21 3 8"></polyline><rect x="1" y="3" width="22" height="5"></rect><line x1="10" y1="12" x2="14" y2="12"></line></svg>`,
  code: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>`,
  file: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path><polyline points="13 2 13 9 20 9"></polyline></svg>`,
};

// --- Initialization ---

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  setupTabs();
  fetchServerInfo();
  fetchSafeFolders();
  fetchClipboard();
  setupUploadEvents();
  setupSSE();
  setupModalEvents();
  setupFaqEvents();
});

// --- Theme Toggle ---

function initTheme() {
  const saved = localStorage.getItem("landrop_theme");
  if (saved === "light") {
    document.body.classList.remove("theme-dark");
    document.body.classList.add("theme-light");
  }
  btnThemeToggle.addEventListener("click", () => {
    if (document.body.classList.contains("theme-light")) {
      document.body.classList.remove("theme-light");
      document.body.classList.add("theme-dark");
      localStorage.setItem("landrop_theme", "dark");
    } else {
      document.body.classList.remove("theme-dark");
      document.body.classList.add("theme-light");
      localStorage.setItem("landrop_theme", "light");
    }
  });
}

// --- Tabs Management ---

function setupTabs() {
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabPanes = document.querySelectorAll(".tab-pane");

  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-tab");
      tabBtns.forEach((b) => b.classList.remove("active"));
      tabPanes.forEach((p) => p.classList.remove("active"));

      btn.classList.add("active");
      const targetPane = document.getElementById(targetId);
      if (targetPane) targetPane.classList.add("active");

      if (targetId === "tab-received") {
        fetchReceivedFiles();
      } else if (targetId === "tab-clipboard") {
        fetchClipboard();
      }
    });
  });
}

// --- Toast Notifications ---

function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerText = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(10px)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// --- Server Info ---

async function fetchServerInfo() {
  try {
    const res = await fetch("/api/info");
    if (!res.ok) return;
    serverInfo = await res.json();

    const hostLabel = serverInfo.landrop_url || `${serverInfo.hostname}.local`;
    hostNameDisplay.innerText = hostLabel;
    qrUrlText.innerText = serverInfo.landrop_url || serverInfo.primary_url;

    const faqDirectIp = document.getElementById("faqDirectIpDisplay");
    if (faqDirectIp && serverInfo.primary_url) {
      faqDirectIp.innerText = serverInfo.primary_url;
    }
  } catch (e) {
    hostNameDisplay.innerText = "Offline / Connection Error";
  }
}

// Click on host pill copies the permanent URL
hostPill.addEventListener("click", async () => {
  const url = serverInfo?.landrop_url || "http://landrop.local:5000";
  try {
    await navigator.clipboard.writeText(url);
    showToast("✓ Copied " + url + " to clipboard!", "success");
  } catch (e) {
    showToast(url, "info");
  }
});

// --- Safe List Folder Explorer ---

function getParentSubpath(subpath) {
  if (!subpath) return "";
  const normalized = subpath.replace(/\\/g, "/").replace(/\/+$/, "");
  const parts = normalized.split("/").filter(Boolean);
  parts.pop();
  return parts.join("/");
}

function showAllSafeFolders(pushHistory = true) {
  currentFolderId = "";
  currentSubpath = "";
  if (selectSafeFolder) selectSafeFolder.value = "";
  if (btnDownloadFolderZip) btnDownloadFolderZip.style.display = "none";
  if (btnSafeBack) btnSafeBack.style.display = "none";

  breadcrumbBar.innerHTML = `<span class="breadcrumb-item active"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px;height:14px;vertical-align:-2px;margin-right:4px;"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>Shared Safe Folders</span>`;

  if (pushHistory) {
    window.history.pushState({ view: "safelist_root" }, "", window.location.pathname);
  }

  safeFilesContainer.innerHTML = "";
  if (!cachedSafeFolders || cachedSafeFolders.length === 0) {
    renderSafeEmptyState("No folders have been added to the Safe List on the host PC yet.");
    return;
  }

  cachedSafeFolders.forEach((f) => {
    const card = document.createElement("div");
    card.className = "file-card safelist-root-folder";

    const top = document.createElement("div");
    top.className = "file-card-top";

    const iconDiv = document.createElement("div");
    iconDiv.className = "file-icon folder";
    iconDiv.innerHTML = categoryIcons.folder;

    const details = document.createElement("div");
    details.className = "file-details";

    const name = document.createElement("div");
    name.className = "file-name";
    name.title = f.name;
    name.innerText = f.name;

    const meta = document.createElement("div");
    meta.className = "file-meta";
    meta.innerText = `${f.item_count || 0} items • Shared PC Folder`;

    details.appendChild(name);
    details.appendChild(meta);
    top.appendChild(iconDiv);
    top.appendChild(details);
    card.appendChild(top);

    const actions = document.createElement("div");
    actions.className = "file-card-actions";
    const openBtn = document.createElement("button");
    openBtn.className = "card-action-btn";
    openBtn.innerHTML = `<span>Browse Folder</span>`;
    actions.appendChild(openBtn);
    card.appendChild(actions);

    card.addEventListener("click", () => {
      selectSafeFolder.value = f.id;
      browseSafeFolder(f.id, "");
    });

    safeFilesContainer.appendChild(card);
  });
}

async function fetchSafeFolders() {
  try {
    const res = await fetch("/api/safelist");
    if (!res.ok) return;
    const data = await res.json();
    cachedSafeFolders = data.folders || [];

    badgeSafeCount.innerText = cachedSafeFolders.length;
    selectSafeFolder.innerHTML = "";

    if (cachedSafeFolders.length === 0) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.innerText = "No folders added to Safe List on PC";
      selectSafeFolder.appendChild(opt);
      renderSafeEmptyState("No folders have been added to the Safe List on the host PC yet.");
      if (btnSafeBack) btnSafeBack.style.display = "none";
      return;
    }

    const allOpt = document.createElement("option");
    allOpt.value = "";
    allOpt.innerText = "📁 All Shared Safe Folders";
    selectSafeFolder.appendChild(allOpt);

    cachedSafeFolders.forEach((f) => {
      const opt = document.createElement("option");
      opt.value = f.id;
      opt.innerText = `📂 ${f.name} (${f.item_count} items)`;
      selectSafeFolder.appendChild(opt);
    });

    // Auto-select folder or show root list
    if (!currentFolderId) {
      if (cachedSafeFolders.length === 1) {
        currentFolderId = cachedSafeFolders[0].id;
        currentSubpath = "";
        selectSafeFolder.value = currentFolderId;
        browseSafeFolder(currentFolderId, "", false);
      } else {
        showAllSafeFolders(false);
      }
    } else {
      selectSafeFolder.value = currentFolderId;
      browseSafeFolder(currentFolderId, currentSubpath, false);
    }
  } catch (e) {
    renderSafeEmptyState("Error loading safe list folders.");
  }
}

selectSafeFolder.addEventListener("change", (e) => {
  currentFolderId = e.target.value;
  currentSubpath = "";
  if (currentFolderId) {
    browseSafeFolder(currentFolderId, "");
  } else {
    showAllSafeFolders();
  }
});

btnRefreshSafe.addEventListener("click", () => {
  if (currentFolderId) {
    browseSafeFolder(currentFolderId, currentSubpath);
  } else {
    fetchSafeFolders();
  }
});

btnDownloadFolderZip.addEventListener("click", () => {
  if (!currentFolderId) return;
  const url = `/api/safelist/download-zip?folder_id=${encodeURIComponent(currentFolderId)}&subpath=${encodeURIComponent(currentSubpath)}`;
  window.location.href = url;
  showToast("Preparing ZIP archive for download...", "info");
});

if (btnSafeBack) {
  btnSafeBack.addEventListener("click", () => {
    if (currentSubpath) {
      browseSafeFolder(currentFolderId, getParentSubpath(currentSubpath));
    } else {
      showAllSafeFolders();
    }
  });
}

// Browser back/forward navigation support
window.addEventListener("popstate", (e) => {
  if (e.state) {
    if (e.state.view === "safelist_folder" && e.state.folderId) {
      browseSafeFolder(e.state.folderId, e.state.subpath || "", false);
    } else if (e.state.view === "safelist_root") {
      showAllSafeFolders(false);
    }
  }
});

async function browseSafeFolder(folderId, subpath = "", pushHistory = true) {
  if (!folderId) {
    showAllSafeFolders(pushHistory);
    return;
  }

  currentFolderId = folderId;
  currentSubpath = subpath;
  if (selectSafeFolder) selectSafeFolder.value = folderId;
  if (btnDownloadFolderZip) btnDownloadFolderZip.style.display = "inline-flex";

  // Update Back button state
  if (btnSafeBack) {
    btnSafeBack.style.display = "inline-flex";
    if (subpath) {
      safeBackBtnLabel.innerText = "Back";
      btnSafeBack.title = "Go up to parent directory";
    } else {
      safeBackBtnLabel.innerText = "All Folders";
      btnSafeBack.title = "Back to all shared safe folders";
    }
  }

  if (pushHistory) {
    window.history.pushState({ view: "safelist_folder", folderId, subpath }, "", window.location.pathname);
  }

  try {
    const url = `/api/safelist/browse?folder_id=${encodeURIComponent(folderId)}&subpath=${encodeURIComponent(subpath)}`;
    const res = await fetch(url);
    if (!res.ok) {
      const err = await res.json();
      renderSafeEmptyState(err.error || "Unable to open folder");
      return;
    }

    const data = await res.json();
    renderBreadcrumbs(data.breadcrumbs || []);
    safeItemsCache = data.items || [];
    renderSafeItems(safeItemsCache);
  } catch (e) {
    renderSafeEmptyState("Error browsing folder: " + e.message);
  }
}

function renderBreadcrumbs(crumbs) {
  breadcrumbBar.innerHTML = "";

  // Root Safe List item
  const rootItem = document.createElement("span");
  rootItem.className = "breadcrumb-item";
  rootItem.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px;height:14px;vertical-align:-2px;margin-right:4px;"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>Safe List`;
  rootItem.title = "View all shared safe folders";
  rootItem.addEventListener("click", () => {
    showAllSafeFolders();
  });
  breadcrumbBar.appendChild(rootItem);

  crumbs.forEach((crumb, idx) => {
    const sep = document.createElement("span");
    sep.className = "breadcrumb-separator";
    sep.innerText = "/";
    breadcrumbBar.appendChild(sep);

    const item = document.createElement("span");
    const isLast = (idx === crumbs.length - 1);
    item.className = "breadcrumb-item" + (isLast ? " active" : "");
    item.innerText = crumb.name;
    if (!isLast) {
      item.addEventListener("click", () => {
        browseSafeFolder(currentFolderId, crumb.subpath);
      });
    }
    breadcrumbBar.appendChild(item);
  });
}

function renderSafeItems(items) {
  safeFilesContainer.innerHTML = "";

  // Add Parent Directory item at top if inside a subfolder
  if (currentSubpath) {
    const parentCard = document.createElement("div");
    parentCard.className = "file-card parent-dir-card";

    const top = document.createElement("div");
    top.className = "file-card-top";

    const iconDiv = document.createElement("div");
    iconDiv.className = "file-icon folder parent-icon";
    iconDiv.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 14 4 9 9 4"></polyline><path d="M20 20v-7a4 4 0 0 0-4-4H4"></path></svg>`;

    const details = document.createElement("div");
    details.className = "file-details";

    const name = document.createElement("div");
    name.className = "file-name";
    name.innerText = ".. (Parent Folder)";

    const meta = document.createElement("div");
    meta.className = "file-meta";
    meta.innerText = "Tap to go back one level";

    details.appendChild(name);
    details.appendChild(meta);
    top.appendChild(iconDiv);
    top.appendChild(details);
    parentCard.appendChild(top);

    const actions = document.createElement("div");
    actions.className = "file-card-actions";
    const backBtn = document.createElement("button");
    backBtn.className = "card-action-btn back-action-btn";
    backBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"></polyline></svg><span>Back</span>`;
    actions.appendChild(backBtn);
    parentCard.appendChild(actions);

    parentCard.addEventListener("click", () => {
      browseSafeFolder(currentFolderId, getParentSubpath(currentSubpath));
    });

    safeFilesContainer.appendChild(parentCard);
  }

  if (items.length === 0 && !currentSubpath) {
    renderSafeEmptyState("This folder is empty");
    return;
  }

  items.forEach((item) => {
    const card = document.createElement("div");
    card.className = "file-card";

    const top = document.createElement("div");
    top.className = "file-card-top";

    const iconDiv = document.createElement("div");
    iconDiv.className = `file-icon ${item.category || "file"}`;
    iconDiv.innerHTML = categoryIcons[item.category] || categoryIcons.file;

    const details = document.createElement("div");
    details.className = "file-details";

    const name = document.createElement("div");
    name.className = "file-name";
    name.title = item.name;
    name.innerText = item.name;

    const meta = document.createElement("div");
    meta.className = "file-meta";
    meta.innerText = item.is_dir ? "Folder" : `${item.formatted_size} • ${item.modified}`;

    details.appendChild(name);
    details.appendChild(meta);
    top.appendChild(iconDiv);
    top.appendChild(details);
    card.appendChild(top);

    // Actions
    const actions = document.createElement("div");
    actions.className = "file-card-actions";

    if (item.is_dir) {
      const openBtn = document.createElement("button");
      openBtn.className = "card-action-btn";
      openBtn.innerHTML = `<span>Open Folder</span>`;
      actions.appendChild(openBtn);

      card.addEventListener("click", () => {
        browseSafeFolder(currentFolderId, item.subpath);
      });
    } else {
      // Preview button for media/documents
      const previewBtn = document.createElement("button");
      previewBtn.className = "card-action-btn";
      previewBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg><span>Preview</span>`;
      previewBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        openPreviewModal(item.name, item.category, `/api/safelist/preview?folder_id=${encodeURIComponent(currentFolderId)}&subpath=${encodeURIComponent(item.subpath)}`, `/api/safelist/download?folder_id=${encodeURIComponent(currentFolderId)}&subpath=${encodeURIComponent(item.subpath)}`);
      });
      actions.appendChild(previewBtn);

      // Download button
      const dlBtn = document.createElement("button");
      dlBtn.className = "card-action-btn";
      dlBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg><span>Download</span>`;
      dlBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        window.location.href = `/api/safelist/download?folder_id=${encodeURIComponent(currentFolderId)}&subpath=${encodeURIComponent(item.subpath)}`;
      });
      actions.appendChild(dlBtn);

      card.addEventListener("click", () => {
        openPreviewModal(item.name, item.category, `/api/safelist/preview?folder_id=${encodeURIComponent(currentFolderId)}&subpath=${encodeURIComponent(item.subpath)}`, `/api/safelist/download?folder_id=${encodeURIComponent(currentFolderId)}&subpath=${encodeURIComponent(item.subpath)}`);
      });
    }

    card.appendChild(actions);
    safeFilesContainer.appendChild(card);
  });
}

function renderSafeEmptyState(msg) {
  safeFilesContainer.innerHTML = `
    <div class="empty-state">
      <div class="empty-state-icon-wrap">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
        </svg>
      </div>
      <p>${msg}</p>
    </div>
  `;
}

// Search Filter
safeSearchInput.addEventListener("input", (e) => {
  const query = e.target.value.toLowerCase().trim();
  if (!query) {
    renderSafeItems(safeItemsCache);
    return;
  }
  const filtered = safeItemsCache.filter((item) => item.name.toLowerCase().includes(query));
  renderSafeItems(filtered);
});

// --- Send to PC (Auto-Save Upload) ---

function setupUploadEvents() {
  const btnSelectMedia = document.getElementById("btnSelectMedia");
  const mediaInput = document.getElementById("mediaInput");

  if (btnSelectMedia && mediaInput) {
    btnSelectMedia.addEventListener("click", () => mediaInput.click());
    mediaInput.addEventListener("change", () => {
      if (mediaInput.files.length > 0) {
        uploadFiles(Array.from(mediaInput.files));
        mediaInput.value = "";
      }
    });
  }

  btnSelectFiles.addEventListener("click", () => fileInput.click());
  if (btnSelectFolder) {
    btnSelectFolder.addEventListener("click", () => folderInput.click());
  }

  fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) {
      uploadFiles(Array.from(fileInput.files));
      fileInput.value = "";
    }
  });

  folderInput.addEventListener("change", () => {
    if (folderInput.files.length > 0) {
      uploadFiles(Array.from(folderInput.files));
      folderInput.value = "";
    }
  });

  // Drag & Drop
  ["dragenter", "dragover"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add("drag-over");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove("drag-over");
    });
  });

  dropzone.addEventListener("drop", (e) => {
    const dt = e.dataTransfer;
    if (dt && dt.files && dt.files.length > 0) {
      uploadFiles(Array.from(dt.files));
    }
  });
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  return (bytes / (1024 * 1024 * 1024)).toFixed(2) + " GB";
}

function uploadFiles(files) {
  if (!files || files.length === 0) return;

  uploadProgressCard.classList.remove("hidden");
  const formData = new FormData();
  let totalBytes = 0;

  files.forEach((f) => {
    formData.append("files", f);
    totalBytes += f.size;
  });

  const label = files.length === 1 ? files[0].name : `${files.length} files (${formatBytes(totalBytes)})`;
  progressFileName.innerText = label;
  progressBarFill.style.width = "0%";
  progressPct.innerText = "0%";

  const startTime = Date.now();
  const xhr = new XMLHttpRequest();

  xhr.upload.addEventListener("progress", (e) => {
    if (e.lengthComputable) {
      const pct = Math.round((e.loaded / e.total) * 100);
      progressBarFill.style.width = pct + "%";
      progressPct.innerText = pct + "%";

      const elapsedSec = (Date.now() - startTime) / 1000;
      if (elapsedSec > 0.3) {
        const bytesPerSec = e.loaded / elapsedSec;
        progressSpeed.innerText = `${formatBytes(bytesPerSec)}/s`;
        const remainingBytes = e.total - e.loaded;
        const etaSec = Math.round(remainingBytes / bytesPerSec);
        progressEta.innerText = `ETA: ${etaSec}s`;
      }
      progressTransferred.innerText = `${formatBytes(e.loaded)} / ${formatBytes(e.total)}`;
    }
  });

  xhr.addEventListener("load", () => {
    if (xhr.status >= 200 && xhr.status < 300) {
      const resp = JSON.parse(xhr.responseText);
      showToast(`✓ Auto-saved ${resp.saved_count} file(s) to PC!`, "success");
      progressBarFill.style.width = "100%";
      progressPct.innerText = "100%";
      progressSpeed.innerText = "Completed";
      progressEta.innerText = "Auto-saved to host PC";

      // Append to sent history list
      if (resp.saved_files) {
        resp.saved_files.forEach((sf) => addSentHistoryItem(sf));
      }

      setTimeout(() => {
        uploadProgressCard.classList.add("hidden");
      }, 3500);

      fetchReceivedFiles();
    } else {
      showToast("Upload failed: " + xhr.statusText, "error");
      progressSpeed.innerText = "Failed";
    }
  });

  xhr.addEventListener("error", () => {
    showToast("Network error during upload", "error");
    progressSpeed.innerText = "Network Error";
  });

  xhr.open("POST", "/api/upload");
  xhr.send(formData);
}

function addSentHistoryItem(fileInfo) {
  const emptySent = sentList.querySelector(".empty-sent");
  if (emptySent) emptySent.remove();

  const item = document.createElement("div");
  item.className = "sent-item";
  item.innerHTML = `
    <div class="sent-item-left">
      <span class="sent-check">✓</span>
      <strong>${fileInfo.filename}</strong>
      <span class="file-meta">(${fileInfo.formatted_size})</span>
    </div>
    <span class="file-meta">${fileInfo.timestamp}</span>
  `;
  sentList.prepend(item);
}

// --- Received Files Tab ---

async function fetchReceivedFiles() {
  try {
    const res = await fetch("/api/received");
    if (!res.ok) return;
    const data = await res.json();
    receivedPathDesc.innerText = data.save_directory || "Downloads/LANDrop_Received";
    renderReceivedFiles(data.files || []);
  } catch (e) {
    receivedFilesContainer.innerHTML = `<div class="empty-state"><p>Error loading received files</p></div>`;
  }
}

btnRefreshReceived.addEventListener("click", fetchReceivedFiles);

function renderReceivedFiles(files) {
  receivedFilesContainer.innerHTML = "";

  if (files.length === 0) {
    receivedFilesContainer.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon-wrap">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <polyline points="22 12 16 12 14 15 10 15 8 12 2 12"></polyline>
            <path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"></path>
          </svg>
        </div>
        <p>No files currently in PC's auto-save directory</p>
        <span class="empty-state-hint">Files sent from your phone or other devices will show up here automatically.</span>
      </div>
    `;
    return;
  }

  files.forEach((file) => {
    const card = document.createElement("div");
    card.className = "file-card";

    const top = document.createElement("div");
    top.className = "file-card-top";

    const iconDiv = document.createElement("div");
    iconDiv.className = `file-icon ${file.category || "file"}`;
    iconDiv.innerHTML = categoryIcons[file.category] || categoryIcons.file;

    const details = document.createElement("div");
    details.className = "file-details";

    const name = document.createElement("div");
    name.className = "file-name";
    name.title = file.filename;
    name.innerText = file.filename;

    const meta = document.createElement("div");
    meta.className = "file-meta";
    meta.innerText = `${file.formatted_size} • ${file.modified}`;

    details.appendChild(name);
    details.appendChild(meta);
    top.appendChild(iconDiv);
    top.appendChild(details);
    card.appendChild(top);

    const actions = document.createElement("div");
    actions.className = "file-card-actions";

    const dlUrl = `/api/received/download/${encodeURIComponent(file.filename)}`;
    const prevUrl = `/api/received/preview/${encodeURIComponent(file.filename)}`;

    const prevBtn = document.createElement("button");
    prevBtn.className = "card-action-btn";
    prevBtn.innerHTML = `<span>Preview</span>`;
    prevBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openPreviewModal(file.filename, file.category, prevUrl, dlUrl);
    });
    actions.appendChild(prevBtn);

    const dlBtn = document.createElement("button");
    dlBtn.className = "card-action-btn";
    dlBtn.innerHTML = `<span>Download</span>`;
    dlBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      window.location.href = dlUrl;
    });
    actions.appendChild(dlBtn);

    card.appendChild(actions);
    card.addEventListener("click", () => {
      openPreviewModal(file.filename, file.category, prevUrl, dlUrl);
    });

    receivedFilesContainer.appendChild(card);
  });
}

// --- Shared Clipboard ---

async function fetchClipboard() {
  try {
    const res = await fetch("/api/clipboard");
    if (!res.ok) return;
    const data = await res.json();
    if (data.text !== undefined && data.text !== clipboardTextarea.value) {
      clipboardTextarea.value = data.text;
    }
    if (data.updated_at) {
      clipboardUpdatedTime.innerText = `Last synced: ${data.updated_at}`;
    }
  } catch (e) {
    console.error("Clipboard fetch error:", e);
  }
}

btnSendClipboard.addEventListener("click", async () => {
  const text = clipboardTextarea.value;
  try {
    const res = await fetch("/api/clipboard", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (res.ok) {
      showToast("✓ Clipboard synced to PC & all devices!", "success");
    }
  } catch (e) {
    showToast("Failed to sync clipboard", "error");
  }
});

btnCopyClipboard.addEventListener("click", async () => {
  const text = clipboardTextarea.value;
  if (!text) {
    showToast("Clipboard is empty", "info");
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    showToast("✓ Copied to your device's clipboard!", "success");
  } catch (e) {
    // Fallback for older browsers
    clipboardTextarea.select();
    document.execCommand("copy");
    showToast("✓ Copied to clipboard!", "success");
  }
});

// --- Real-Time SSE Setup ---

function setupSSE() {
  if (!window.EventSource) return;

  const eventSource = new EventSource("/api/events");

  eventSource.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      if (data.type === "file_received") {
        showToast(`Incoming file auto-saved: ${data.file.filename}`, "info");
        fetchReceivedFiles();
      } else if (data.type === "clipboard_updated") {
        clipboardTextarea.value = data.text;
        clipboardUpdatedTime.innerText = `Synced just now (${data.updated_at})`;
      }
    } catch (err) {
      // heartbeats or non-json messages
    }
  };

  eventSource.onerror = () => {
    // Reconnects automatically
  };
}

// --- Modals Setup ---

function setupModalEvents() {
  // Preview Modal
  btnClosePreview.addEventListener("click", () => previewModal.classList.add("hidden"));
  previewModal.addEventListener("click", (e) => {
    if (e.target === previewModal) previewModal.classList.add("hidden");
  });

  // QR Modal
  btnQrModal.addEventListener("click", () => qrModal.classList.remove("hidden"));
  btnCloseQr.addEventListener("click", () => qrModal.classList.add("hidden"));
  qrModal.addEventListener("click", (e) => {
    if (e.target === qrModal) qrModal.classList.add("hidden");
  });

  // ESC key closes modals
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      previewModal.classList.add("hidden");
      qrModal.classList.add("hidden");
    }
  });
}

async function openPreviewModal(title, category, previewUrl, downloadUrl) {
  previewModalTitle.innerText = title;
  previewModalBody.innerHTML = "<p>Loading preview...</p>";
  btnModalDownload.href = downloadUrl;
  previewModal.classList.remove("hidden");

  if (category === "image") {
    previewModalBody.innerHTML = `<img src="${previewUrl}" alt="${title}" />`;
  } else if (category === "video") {
    previewModalBody.innerHTML = `<video src="${previewUrl}" controls autoplay playsinline></video>`;
  } else if (category === "audio") {
    previewModalBody.innerHTML = `<audio src="${previewUrl}" controls autoplay></audio>`;
  } else if (category === "code" || category === "document") {
    try {
      const res = await fetch(previewUrl);
      const text = await res.text();
      // Show first 50KB if huge
      const snippet = text.length > 50000 ? text.slice(0, 50000) + "\n\n... (file preview truncated)" : text;
      previewModalBody.innerHTML = `<pre><code>${escapeHtml(snippet)}</code></pre>`;
    } catch (e) {
      previewModalBody.innerHTML = `<p>Unable to preview this file inline.</p>`;
    }
  } else {
    previewModalBody.innerHTML = `<p>Preview not available for this file type. Click below to download.</p>`;
  }
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// --- Help & Device FAQ Setup ---

function setupFaqEvents() {
  const faqItems = document.querySelectorAll(".faq-item");
  faqItems.forEach((item) => {
    const question = item.querySelector(".faq-question");
    if (question) {
      question.addEventListener("click", () => {
        item.classList.toggle("open");
      });
    }
  });

  const btnFaqNav = document.getElementById("btnFaqNav");
  if (btnFaqNav) {
    btnFaqNav.addEventListener("click", () => {
      const tabBtns = document.querySelectorAll(".tab-btn");
      const tabPanes = document.querySelectorAll(".tab-pane");
      tabBtns.forEach((b) => b.classList.remove("active"));
      tabPanes.forEach((p) => p.classList.remove("active"));

      const faqBtn = document.querySelector('.tab-btn[data-tab="tab-faq"]');
      const faqPane = document.getElementById("tab-faq");
      if (faqBtn) faqBtn.classList.add("active");
      if (faqPane) {
        faqPane.classList.add("active");
        faqPane.scrollIntoView({ behavior: "smooth" });
      }
    });
  }
}
