<script setup lang="ts">
import { ref, reactive, computed, watch } from "vue";
import { invoke } from "@tauri-apps/api/core";
import { open, save } from "@tauri-apps/plugin-dialog";
import {
  NButton,
  NCard,
  NCollapse,
  NCollapseItem,
  NForm,
  NFormItem,
  NGrid,
  NGridItem,
  NImage,
  NInput,
  NInputNumber,
  NPopover,
  NSelect,
  NSlider,
  NSpace,
  NSwitch,
} from "naive-ui";
import { useI18n } from "vue-i18n";

const { t, locale } = useI18n();

type RefineMethod = "watershed" | "border-grow" | "contour" | "threshold";

const form = reactive({
  inputPath: "",
  outputPath: "",
  threshold: 245,
  width: 40,
  height: 40,
  refineMethod: "watershed" as RefineMethod,
  morphKernelSize: 1,
  contourExpand: 0,
  bgTolerance: 12
});

const realtimePreview = ref(true);
const previewDataUrl = ref("");
const status = ref("");
const advancedExpanded = ref<string[]>([]);
const previewLoading = ref(false);
const processLoading = ref(false);
let debounceTimer: number | null = null;
let previewToken = 0;
let previewInFlight = false;
let previewQueued = false;
const fastPreview = ref(true);
const previewMaxSide = ref(720);
const previewCodec = ref<"jpeg" | "png">("jpeg");
const previewQuality = ref(85);
const tipVisible = reactive<Record<string, boolean>>({});

function showTip(id: string) {
  tipVisible[id] = true;
}

function hideTip(id: string) {
  tipVisible[id] = false;
}

function toggleTip(id: string) {
  tipVisible[id] = !tipVisible[id];
}

const methodOptions = computed(() => [
  { label: "watershed", value: "watershed" },
  { label: "border-grow", value: "border-grow" },
  { label: "contour", value: "contour" },
  { label: "threshold", value: "threshold" }
]);

function applyRecommend() {
  const map: Record<RefineMethod, { threshold: number; morph: number; expand: number; bg: number }> = {
    watershed: { threshold: 245, morph: 1, expand: 0, bg: 12 },
    "border-grow": { threshold: 110, morph: 1, expand: 0, bg: 12 },
    contour: { threshold: 235, morph: 1, expand: 0, bg: 12 },
    threshold: { threshold: 235, morph: 1, expand: 0, bg: 12 }
  };
  const rec = map[form.refineMethod];
  form.threshold = rec.threshold;
  form.morphKernelSize = rec.morph;
  form.contourExpand = rec.expand;
  form.bgTolerance = rec.bg;
  schedulePreview(0, true);
}

async function browseInput() {
  const selected = await open({
    multiple: false,
    filters: [{ name: "Image files", extensions: ["png", "jpg", "jpeg", "bmp", "webp"] }]
  });
  if (typeof selected === "string") {
    form.inputPath = selected;
    status.value = `${t("input")} selected`;
    schedulePreview(0, true);
  }
}

async function browseOutput() {
  const selected = await save({
    filters: [{ name: "PNG", extensions: ["png"] }]
  });
  if (typeof selected === "string") {
    form.outputPath = selected;
    status.value = `${t("output")} selected`;
  }
}

async function runPreview() {
  if (!form.inputPath) return;
  if (previewInFlight) {
    previewQueued = true;
    status.value = "Preview queued...";
    return;
  }

  const token = ++previewToken;
  previewInFlight = true;
  previewLoading.value = true;
  status.value = "Previewing...";
  try {
    const dataUrl = await invoke<string>("preview_image", {
      inputPath: form.inputPath,
      threshold: form.threshold,
      width: form.width,
      height: form.height,
      refineMethod: form.refineMethod,
      morphKernelSize: form.morphKernelSize,
      contourExpand: form.contourExpand,
      bgTolerance: form.bgTolerance,
      fastPreview: fastPreview.value,
      previewMaxSide: previewMaxSide.value,
      previewCodec: previewCodec.value,
      previewQuality: previewQuality.value
    });
    if (token !== previewToken) return;
    previewDataUrl.value = dataUrl;
    status.value = "Preview ready";
  } catch (err) {
    status.value = `Preview failed: ${String(err)}`;
  } finally {
    previewInFlight = false;
    previewLoading.value = false;
    if (previewQueued) {
      previewQueued = false;
      schedulePreview(0, true);
    }
  }
}

async function processAndSave() {
  if (!form.inputPath || !form.outputPath) {
    status.value = "Please select input/output path";
    return;
  }
  processLoading.value = true;
  status.value = "Processing...";
  try {
    const dataUrl = await invoke<string>("process_and_save", {
      inputPath: form.inputPath,
      outputPath: form.outputPath,
      threshold: form.threshold,
      width: form.width,
      height: form.height,
      refineMethod: form.refineMethod,
      morphKernelSize: form.morphKernelSize,
      contourExpand: form.contourExpand,
      bgTolerance: form.bgTolerance
    });
    previewDataUrl.value = dataUrl;
    status.value = `Saved: ${form.outputPath}`;
  } catch (err) {
    status.value = `Process failed: ${String(err)}`;
  } finally {
    processLoading.value = false;
  }
}

function schedulePreview(delayMs = 280, force = false) {
  if (!force && !realtimePreview.value) return;
  if (debounceTimer !== null) window.clearTimeout(debounceTimer);
  debounceTimer = window.setTimeout(() => {
    runPreview();
  }, delayMs);
}

watch(
  () => ({
    inputPath: form.inputPath,
    width: form.width,
    height: form.height,
    refineMethod: form.refineMethod,
    morphKernelSize: form.morphKernelSize,
    contourExpand: form.contourExpand,
    bgTolerance: form.bgTolerance
  }),
  () => schedulePreview(120),
  { deep: true }
);

watch(
  () => form.threshold,
  () => schedulePreview(280),
  { deep: true }
);
</script>

<template>
  <n-space vertical size="large" style="padding: 16px">
    <n-grid :cols="24" :x-gap="16" :y-gap="16" responsive="screen">
      <n-grid-item :span="15">
        <n-card :title="t('title')">
          <n-space justify="space-between" align="center" style="margin-bottom: 12px">
            <n-space align="center">
              <span>{{ t("realtime") }}</span>
              <n-popover trigger="manual" :show="!!tipVisible.realtime">
                <template #trigger>
                  <span
                    class="tip-mark"
                    @mouseenter="showTip('realtime')"
                    @mouseleave="hideTip('realtime')"
                    @click.stop="toggleTip('realtime')"
                  >?</span>
                </template>
                {{ t("tipRealtime") }}
              </n-popover>
              <n-switch v-model:value="realtimePreview" />
            </n-space>
            <n-select v-model:value="locale" :options="[{ label: '中文', value: 'zh-CN' }, { label: 'English', value: 'en' }]" style="width: 140px" />
          </n-space>

          <n-form label-placement="left" label-width="110">
            <n-form-item :label="t('input')">
              <n-input v-model:value="form.inputPath" />
              <n-button @click="browseInput" style="margin-left: 8px">{{ t("browse") }}</n-button>
            </n-form-item>
            <n-form-item :label="t('output')">
              <n-input v-model:value="form.outputPath" />
              <n-button @click="browseOutput" style="margin-left: 8px">{{ t("browse") }}</n-button>
            </n-form-item>
            <n-form-item :label="t('method')">
              <template #label>
                <n-space align="center" size="small">
                  <span>{{ t("method") }}</span>
                  <n-popover trigger="manual" :show="!!tipVisible.method">
                    <template #trigger>
                      <span
                        class="tip-mark"
                        @mouseenter="showTip('method')"
                        @mouseleave="hideTip('method')"
                        @click.stop="toggleTip('method')"
                      >?</span>
                    </template>
                    {{ t("tipMethod") }}
                  </n-popover>
                </n-space>
              </template>
              <n-select v-model:value="form.refineMethod" :options="methodOptions" />
            </n-form-item>
            <n-form-item :label="t('threshold')">
              <template #label>
                <n-space align="center" size="small">
                  <span>{{ t("threshold") }}</span>
                  <n-popover trigger="manual" :show="!!tipVisible.threshold">
                    <template #trigger>
                      <span
                        class="tip-mark"
                        @mouseenter="showTip('threshold')"
                        @mouseleave="hideTip('threshold')"
                        @click.stop="toggleTip('threshold')"
                      >?</span>
                    </template>
                    {{ t("tipThreshold") }}
                  </n-popover>
                </n-space>
              </template>
              <n-slider
                v-model:value="form.threshold"
                :min="0"
                :max="255"
                style="flex: 1"
                @mouseup="schedulePreview(0, true)"
                @touchend="schedulePreview(0, true)"
              />
              <n-input-number v-model:value="form.threshold" :min="0" :max="255" style="width: 100px; margin-left: 8px" />
            </n-form-item>
            <n-form-item :label="t('canvas')">
              <template #label>
                <n-space align="center" size="small">
                  <span>{{ t("canvas") }}</span>
                  <n-popover trigger="manual" :show="!!tipVisible.canvas">
                    <template #trigger>
                      <span
                        class="tip-mark"
                        @mouseenter="showTip('canvas')"
                        @mouseleave="hideTip('canvas')"
                        @click.stop="toggleTip('canvas')"
                      >?</span>
                    </template>
                    {{ t("tipCanvas") }}
                  </n-popover>
                </n-space>
              </template>
              <n-input-number v-model:value="form.width" :min="1" />
              <span style="margin: 0 8px">x</span>
              <n-input-number v-model:value="form.height" :min="1" />
            </n-form-item>
          </n-form>

          <n-collapse v-model:expanded-names="advancedExpanded">
            <n-collapse-item :title="t('advanced')" name="advanced">
              <n-form label-placement="left" label-width="110">
                <n-form-item :label="t('morph')">
                  <template #label>
                    <n-space align="center" size="small">
                      <span>{{ t("morph") }}</span>
                      <n-popover trigger="manual" :show="!!tipVisible.morph">
                        <template #trigger>
                          <span
                            class="tip-mark"
                            @mouseenter="showTip('morph')"
                            @mouseleave="hideTip('morph')"
                            @click.stop="toggleTip('morph')"
                          >?</span>
                        </template>
                        {{ t("tipMorph") }}
                      </n-popover>
                    </n-space>
                  </template>
                  <n-input-number v-model:value="form.morphKernelSize" :min="1" :step="2" />
                </n-form-item>
                <n-form-item :label="t('expand')">
                  <template #label>
                    <n-space align="center" size="small">
                      <span>{{ t("expand") }}</span>
                      <n-popover trigger="manual" :show="!!tipVisible.expand">
                        <template #trigger>
                          <span
                            class="tip-mark"
                            @mouseenter="showTip('expand')"
                            @mouseleave="hideTip('expand')"
                            @click.stop="toggleTip('expand')"
                          >?</span>
                        </template>
                        {{ t("tipExpand") }}
                      </n-popover>
                    </n-space>
                  </template>
                  <n-input-number v-model:value="form.contourExpand" :min="0" />
                </n-form-item>
                <n-form-item :label="t('bgTolerance')">
                  <template #label>
                    <n-space align="center" size="small">
                      <span>{{ t("bgTolerance") }}</span>
                      <n-popover trigger="manual" :show="!!tipVisible.bgTolerance">
                        <template #trigger>
                          <span
                            class="tip-mark"
                            @mouseenter="showTip('bgTolerance')"
                            @mouseleave="hideTip('bgTolerance')"
                            @click.stop="toggleTip('bgTolerance')"
                          >?</span>
                        </template>
                        {{ t("tipBgTolerance") }}
                      </n-popover>
                    </n-space>
                  </template>
                  <n-input-number v-model:value="form.bgTolerance" :min="0" :disabled="form.refineMethod !== 'watershed'" />
                </n-form-item>
              </n-form>
            </n-collapse-item>
          </n-collapse>

          <n-space justify="end" style="margin-top: 16px">
            <n-popover trigger="manual" :show="!!tipVisible.applyRecommend">
              <template #trigger>
                <span
                  @mouseenter="showTip('applyRecommend')"
                  @mouseleave="hideTip('applyRecommend')"
                  @click.stop="toggleTip('applyRecommend')"
                >
                  <n-button @click="applyRecommend">{{ t("applyRecommend") }}</n-button>
                </span>
              </template>
              {{ t("tipApplyRecommend") }}
            </n-popover>
            <n-button type="primary" :loading="previewLoading" @click="runPreview">{{ t("preview") }}</n-button>
            <n-button type="primary" secondary :loading="processLoading" @click="processAndSave">{{ t("process") }}</n-button>
          </n-space>
        </n-card>
      </n-grid-item>

      <n-grid-item :span="9">
        <n-card :title="t('preview')">
          <div style="min-height: 36px">{{ status }}</div>
          <n-image v-if="previewDataUrl" :src="previewDataUrl" object-fit="contain" width="100%" />
        </n-card>
      </n-grid-item>
    </n-grid>
  </n-space>
</template>

<style scoped>
.tip-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 1px solid #999;
  font-size: 11px;
  line-height: 1;
  cursor: help;
  color: #666;
}
</style>
