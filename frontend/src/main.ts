import { createApp } from "vue";
import { createI18n } from "vue-i18n";
import App from "./App.vue";

const messages = {
  "zh-CN": {
    title: "自动绿幕工具",
    input: "输入图片",
    output: "输出图片",
    browse: "浏览",
    preview: "预览",
    process: "处理并保存",
    method: "算法",
    threshold: "阈值",
    canvas: "画布",
    advanced: "进阶参数",
    realtime: "实时渲染",
    applyRecommend: "应用推荐参数",
    morph: "形态学核",
    expand: "轮廓外扩",
    bgTolerance: "背景容差",
    tipRealtime: "开启后参数变化会自动触发预览，关闭后仅手动预览。",
    tipMethod: "watershed 适合复杂背景；border-grow 适合边缘明显场景；contour 适合主体轮廓清晰；threshold 速度最快。",
    tipThreshold: "主体亮度阈值。值越高保留区域越少，值越低保留区域越多。",
    tipCanvas: "输出固定画布大小（宽 x 高），主体保持居中。",
    tipMorph: "形态学核用于去噪与连通区域平滑，建议保持奇数。",
    tipExpand: "在主轮廓外额外扩张像素，避免边缘被切掉。",
    tipBgTolerance: "仅对 watershed 生效，控制背景种子容差，越大越容易判为背景。",
    tipApplyRecommend: "按当前算法快速套用一组推荐参数。"
  },
  en: {
    title: "Auto Green Background",
    input: "Input Image",
    output: "Output Image",
    browse: "Browse",
    preview: "Preview",
    process: "Process and Save",
    method: "Method",
    threshold: "Threshold",
    canvas: "Canvas",
    advanced: "Advanced",
    realtime: "Realtime Preview",
    applyRecommend: "Apply Recommended",
    morph: "Morph Kernel",
    expand: "Contour Expand",
    bgTolerance: "BG Tolerance",
    tipRealtime: "When enabled, parameter changes auto-trigger preview; otherwise preview runs only manually.",
    tipMethod: "watershed for complex backgrounds; border-grow for clear edges; contour for clean silhouettes; threshold is the fastest.",
    tipThreshold: "Foreground brightness threshold. Higher keeps less; lower keeps more.",
    tipCanvas: "Fixed output canvas size (width x height); foreground stays centered.",
    tipMorph: "Morph kernel smooths/denoises mask regions. Keep odd values.",
    tipExpand: "Expand the main contour outward to avoid edge clipping.",
    tipBgTolerance: "Used only by watershed. Higher values classify more pixels as background.",
    tipApplyRecommend: "Apply a recommended parameter preset for current method."
  }
};

const i18n = createI18n({
  legacy: false,
  locale: navigator.language.toLowerCase().includes("zh") ? "zh-CN" : "en",
  fallbackLocale: "en",
  messages
});

createApp(App).use(i18n).mount("#app");
