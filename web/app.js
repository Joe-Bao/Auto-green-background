const inputPath = document.getElementById("inputPath");
const outputPath = document.getElementById("outputPath");
const threshold = document.getElementById("threshold");
const thresholdValue = document.getElementById("thresholdValue");
const widthInput = document.getElementById("width");
const heightInput = document.getElementById("height");
const refineMethodInput = document.getElementById("refineMethod");
const morphKernelSizeInput = document.getElementById("morphKernelSize");
const contourExpandInput = document.getElementById("contourExpand");
const bgToleranceInput = document.getElementById("bgTolerance");
const realtimePreviewEnabledInput = document.getElementById("realtimePreviewEnabled");
const statusEl = document.getElementById("status");
const previewEl = document.getElementById("preview");
const methodHint = document.getElementById("methodHint");
const languageSelect = document.getElementById("language");
const tooltipPopup = document.getElementById("tooltipPopup");
const bgToleranceDisabledHint = document.getElementById("bgToleranceDisabledHint");
let previewDebounceTimer = null;
let previewToken = 0;

const I18N = {
  "zh-CN": {
    title: "自动绿幕工具",
    ioCardTitle: "输入 / 输出",
    basicCardTitle: "基础参数",
    advancedSummary: "进阶参数（默认收起）",
    previewCardTitle: "预览",
    labelRealtimePreview: "实时渲染",
    labelInput: "输入图片",
    labelOutput: "输出图片",
    labelRefineMethod: "算法",
    labelThreshold: "阈值",
    labelCanvasSize: "画布尺寸",
    labelMorphKernel: "形态学核",
    labelContourExpand: "轮廓外扩",
    labelBgTolerance: "背景容差",
    browse: "浏览",
    preview: "预览",
    process: "处理并保存",
    applyRecommend: "应用推荐参数",
    inputPlaceholder: "选择输入图片",
    outputPlaceholder: "选择输出路径",
    statusInputSelected: "已选择输入图片。",
    statusOutputSelected: "已选择输出路径。",
    statusGenerating: "正在生成预览...",
    statusPreviewReady: "预览完成。",
    statusProcessing: "正在处理图片...",
    statusPreviewFailed: "预览失败。",
    statusProcessFailed: "处理失败。",
    bgToleranceDisabledReason: "仅在 watershed 算法下生效，当前算法已禁用该项。",
    methodHints: {
      watershed: "推荐复杂边界。Threshold 控制前景种子，BG Tolerance 控制背景种子容差。",
      "border-grow": "从四周背景递归生长，遇到低于阈值即停止，适合深色描边分割。",
      contour: "先阈值，再提取最大轮廓。适合主体明显且背景较干净。",
      threshold: "纯阈值快速模式，速度快但容易硬切和漏边。"
    },
    tips: {
      tipRefineMethod: "选择前景分割算法。",
      tipThreshold: "当前算法的主阈值输入。",
      tipCanvasSize: "输出画布大小，主体会居中放置。",
      tipRealtimePreview: "开启后参数变化会自动触发预览；关闭后仅手动预览。",
      tipMorphKernel: "去噪/补洞强度，必须是奇数（1/3/5/7）。",
      tipContourExpand: "向外扩张前景，尽量保住黑边描边。",
      tipBgTolerance: "仅 watershed 使用，边框背景灰度容差。"
    }
  },
  en: {
    title: "Auto Green Background",
    ioCardTitle: "Input / Output",
    basicCardTitle: "Basic",
    advancedSummary: "Advanced Parameters (collapsed by default)",
    previewCardTitle: "Preview",
    labelRealtimePreview: "Realtime Preview",
    labelInput: "Input Image",
    labelOutput: "Output Image",
    labelRefineMethod: "Refine Method",
    labelThreshold: "Threshold",
    labelCanvasSize: "Canvas Size",
    labelMorphKernel: "Morph Kernel",
    labelContourExpand: "Contour Expand",
    labelBgTolerance: "BG Tolerance",
    browse: "Browse",
    preview: "Preview",
    process: "Process and Save",
    applyRecommend: "Apply Recommended",
    inputPlaceholder: "Select input image",
    outputPlaceholder: "Select output path",
    statusInputSelected: "Input selected.",
    statusOutputSelected: "Output selected.",
    statusGenerating: "Generating preview...",
    statusPreviewReady: "Preview ready.",
    statusProcessing: "Processing image...",
    statusPreviewFailed: "Preview failed.",
    statusProcessFailed: "Process failed.",
    bgToleranceDisabledReason: "Only used by watershed. Disabled for current method.",
    methodHints: {
      watershed: "Best for complex edges. Threshold controls FG seeds, BG Tolerance controls BG seeds.",
      "border-grow": "Recursive growth from borders; stop when pixel value drops below threshold.",
      contour: "Threshold then keep largest contour. Good when background is clean.",
      threshold: "Fast pure threshold mode; may hard-cut thin edges."
    },
    tips: {
      tipRefineMethod: "Foreground segmentation algorithm.",
      tipThreshold: "Main threshold input for selected method.",
      tipCanvasSize: "Output canvas size, foreground is centered.",
      tipRealtimePreview: "Auto preview on parameter change. Turn off for manual-only preview.",
      tipMorphKernel: "Noise cleanup strength. Must be odd (1/3/5/7).",
      tipContourExpand: "Expand foreground to preserve dark outlines.",
      tipBgTolerance: "Watershed only. Border background tolerance."
    }
  }
};

function getCurrentLang() {
  return languageSelect.value || "zh-CN";
}

function t(key) {
  const lang = getCurrentLang();
  return I18N[lang][key];
}

function translateUi() {
  const lang = getCurrentLang();
  const m = I18N[lang];
  document.getElementById("title").textContent = m.title;
  document.getElementById("ioCardTitle").textContent = m.ioCardTitle;
  document.getElementById("basicCardTitle").textContent = m.basicCardTitle;
  document.getElementById("advancedSummary").textContent = m.advancedSummary;
  document.getElementById("previewCardTitle").textContent = m.previewCardTitle;
  document.getElementById("labelRealtimePreview").textContent = m.labelRealtimePreview;
  document.getElementById("labelInput").textContent = m.labelInput;
  document.getElementById("labelOutput").textContent = m.labelOutput;
  document.getElementById("labelRefineMethod").textContent = m.labelRefineMethod;
  document.getElementById("labelThreshold").textContent = m.labelThreshold;
  document.getElementById("labelCanvasSize").textContent = m.labelCanvasSize;
  document.getElementById("labelMorphKernel").textContent = m.labelMorphKernel;
  document.getElementById("labelContourExpand").textContent = m.labelContourExpand;
  document.getElementById("labelBgTolerance").textContent = m.labelBgTolerance;

  inputPath.placeholder = m.inputPlaceholder;
  outputPath.placeholder = m.outputPlaceholder;
  document.getElementById("btnInput").textContent = m.browse;
  document.getElementById("btnOutput").textContent = m.browse;
  document.getElementById("btnPreview").textContent = m.preview;
  document.getElementById("btnProcess").textContent = m.process;
  document.getElementById("btnApplyRecommend").textContent = m.applyRecommend;

  bindCustomTooltips();
  updateMethodHint();
  updateParamVisibility();
}

function setStatus(text, isError = false) {
  statusEl.textContent = text;
  statusEl.style.color = isError ? "#b00020" : "#333";
}

function syncThresholdFromSlider() {
  thresholdValue.value = threshold.value;
}

function syncThresholdFromNumber() {
  let v = Number(thresholdValue.value);
  if (Number.isNaN(v)) v = 0;
  v = Math.max(0, Math.min(255, v));
  thresholdValue.value = String(v);
  threshold.value = String(v);
}

function outputDefaultName() {
  if (!inputPath.value) return "output.png";
  const src = inputPath.value.replace(/\\/g, "/");
  const fileName = src.split("/").pop() || "output";
  const dot = fileName.lastIndexOf(".");
  const stem = dot > 0 ? fileName.slice(0, dot) : fileName;
  return `${stem}_green.png`;
}

function parseOddKernelSize(value) {
  let k = Number(value);
  if (Number.isNaN(k) || k < 1) k = 1;
  if (k % 2 === 0) k += 1;
  return String(k);
}

function parseNonNegativeInt(value, fallback = 0) {
  let v = Number(value);
  if (Number.isNaN(v) || v < 0) v = fallback;
  return String(Math.floor(v));
}

function getMethodRecommend(method) {
  const recommends = {
    watershed: {
      threshold: 245,
      morphKernelSize: 1,
      contourExpand: 0,
      bgTolerance: 12
    },
    "border-grow": {
      threshold: 110,
      morphKernelSize: 1,
      contourExpand: 0,
      bgTolerance: 12
    },
    contour: {
      threshold: 235,
      morphKernelSize: 1,
      contourExpand: 0,
      bgTolerance: 12
    },
    threshold: {
      threshold: 235,
      morphKernelSize: 1,
      contourExpand: 0,
      bgTolerance: 12
    }
  };
  return recommends[method] || recommends.watershed;
}

function applyRecommendForCurrentMethod() {
  const rec = getMethodRecommend(refineMethodInput.value);
  threshold.value = String(rec.threshold);
  thresholdValue.value = String(rec.threshold);
  morphKernelSizeInput.value = String(rec.morphKernelSize);
  contourExpandInput.value = String(rec.contourExpand);
  bgToleranceInput.value = String(rec.bgTolerance);
  updateMethodHint();
  schedulePreview(0);
}

function updateMethodHint() {
  const lang = getCurrentLang();
  const method = refineMethodInput.value;
  methodHint.textContent = I18N[lang].methodHints[method] || "";
}

function updateParamVisibility() {
  const method = refineMethodInput.value;
  const showBgTolerance = method === "watershed";
  bgToleranceInput.disabled = !showBgTolerance;
  document.getElementById("labelBgTolerance").style.opacity = showBgTolerance ? "1" : "0.5";
  document.getElementById("tipBgTolerance").style.opacity = showBgTolerance ? "1" : "0.5";
  bgToleranceDisabledHint.textContent = showBgTolerance ? "" : t("bgToleranceDisabledReason");
}

function bindCustomTooltips() {
  const lang = getCurrentLang();
  const tips = I18N[lang].tips;
  document.querySelectorAll(".tip").forEach((tipEl) => {
    tipEl.dataset.tipText = tips[tipEl.id] || "";
    tipEl.removeAttribute("title");
  });
}

function showTooltip(el, event) {
  const text = el.dataset.tipText || "";
  if (!text) return;
  tooltipPopup.textContent = text;
  tooltipPopup.style.display = "block";
  moveTooltip(event);
}

function moveTooltip(event) {
  if (tooltipPopup.style.display !== "block") return;
  const margin = 10;
  const nextX = event.clientX + 12;
  const nextY = event.clientY + 12;
  const maxX = window.innerWidth - tooltipPopup.offsetWidth - margin;
  const maxY = window.innerHeight - tooltipPopup.offsetHeight - margin;
  tooltipPopup.style.left = `${Math.max(margin, Math.min(nextX, maxX))}px`;
  tooltipPopup.style.top = `${Math.max(margin, Math.min(nextY, maxY))}px`;
}

function hideTooltip() {
  tooltipPopup.style.display = "none";
}

function attachTooltipEvents() {
  document.querySelectorAll(".tip").forEach((tipEl) => {
    tipEl.addEventListener("mouseenter", (event) => showTooltip(tipEl, event));
    tipEl.addEventListener("mousemove", moveTooltip);
    tipEl.addEventListener("mouseleave", hideTooltip);
  });
}

async function runPreview() {
  if (!inputPath.value) return;
  const token = ++previewToken;
  setStatus(t("statusGenerating"));
  const res = await window.pywebview.api.preview(
    inputPath.value,
    thresholdValue.value,
    widthInput.value,
    heightInput.value,
    refineMethodInput.value,
    morphKernelSizeInput.value,
    contourExpandInput.value,
    bgToleranceInput.value
  );
  if (token !== previewToken) return;
  if (!res.ok) {
    setStatus(res.error || t("statusPreviewFailed"), true);
    return;
  }
  previewEl.src = res.preview;
  setStatus(t("statusPreviewReady"));
}

function schedulePreview(delayMs = 180, force = false) {
  if (!force && !realtimePreviewEnabledInput.checked) {
    return;
  }
  if (previewDebounceTimer) clearTimeout(previewDebounceTimer);
  previewDebounceTimer = setTimeout(() => {
    runPreview();
  }, delayMs);
}

threshold.addEventListener("input", () => {
  syncThresholdFromSlider();
  schedulePreview();
});
threshold.addEventListener("change", () => schedulePreview(0));
thresholdValue.addEventListener("input", () => {
  syncThresholdFromNumber();
  schedulePreview();
});
thresholdValue.addEventListener("change", () => schedulePreview(0));
morphKernelSizeInput.addEventListener("input", () => {
  morphKernelSizeInput.value = parseOddKernelSize(morphKernelSizeInput.value);
  schedulePreview();
});
contourExpandInput.addEventListener("input", () => {
  contourExpandInput.value = parseNonNegativeInt(contourExpandInput.value, 0);
  schedulePreview();
});
bgToleranceInput.addEventListener("input", () => {
  bgToleranceInput.value = parseNonNegativeInt(bgToleranceInput.value, 12);
  schedulePreview();
});
widthInput.addEventListener("change", () => schedulePreview(0));
heightInput.addEventListener("change", () => schedulePreview(0));
refineMethodInput.addEventListener("change", () => {
  updateMethodHint();
  updateParamVisibility();
  schedulePreview(0);
});
document.getElementById("btnApplyRecommend").addEventListener("click", applyRecommendForCurrentMethod);
languageSelect.addEventListener("change", () => {
  translateUi();
});
realtimePreviewEnabledInput.addEventListener("change", () => {
  if (realtimePreviewEnabledInput.checked) {
    schedulePreview(0, true);
  }
});

document.getElementById("btnInput").addEventListener("click", async () => {
  const p = await window.pywebview.api.select_input_file();
  if (p) {
    inputPath.value = p;
    setStatus(t("statusInputSelected"));
    schedulePreview(0, true);
  }
});

document.getElementById("btnOutput").addEventListener("click", async () => {
  const p = await window.pywebview.api.select_output_file(outputDefaultName());
  if (p) {
    outputPath.value = p;
    setStatus(t("statusOutputSelected"));
  }
});

document.getElementById("btnPreview").addEventListener("click", async () => {
  await runPreview();
});

document.getElementById("btnProcess").addEventListener("click", async () => {
  setStatus(t("statusProcessing"));
  const res = await window.pywebview.api.process_and_save(
    inputPath.value,
    outputPath.value,
    thresholdValue.value,
    widthInput.value,
    heightInput.value,
    refineMethodInput.value,
    morphKernelSizeInput.value,
    contourExpandInput.value,
    bgToleranceInput.value
  );
  if (!res.ok) {
    setStatus(res.error || t("statusProcessFailed"), true);
    return;
  }
  previewEl.src = res.preview;
  setStatus(`Saved: ${res.output_path}`);
});

(() => {
  const prefersZh = (navigator.language || "").toLowerCase().includes("zh");
  languageSelect.value = prefersZh ? "zh-CN" : "en";
  translateUi();
  attachTooltipEvents();
  updateParamVisibility();
  updateMethodHint();
})();
