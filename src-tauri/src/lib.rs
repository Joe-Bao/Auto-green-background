use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStderr, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::mpsc::{self, Sender};
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;
use std::time::Duration;

use serde::{Deserialize, Serialize};
use tauri::Manager;

const BRIDGE_TIMEOUT_MS: u64 = 8_000;

type PendingMap = Arc<Mutex<HashMap<String, Sender<Result<BridgeResponse, String>>>>>;

#[derive(Deserialize)]
struct BridgeResponse {
    id: String,
    ok: bool,
    preview: Option<String>,
    error: Option<String>,
}

#[derive(Serialize)]
struct BridgeRequest<'a> {
    id: String,
    mode: &'a str,
    input: &'a str,
    #[serde(skip_serializing_if = "Option::is_none")]
    output: Option<&'a str>,
    threshold: i32,
    width: i32,
    height: i32,
    refine_method: &'a str,
    morph_kernel_size: i32,
    contour_expand: i32,
    bg_tolerance: i32,
    fast_preview: bool,
    preview_max_side: i32,
    preview_codec: &'a str,
    preview_quality: i32,
}

#[derive(Default)]
struct BridgeState {
    manager: Mutex<BridgeManager>,
}

#[derive(Default)]
struct BridgeManager {
    request_seq: u64,
    process: Option<BridgeProcess>,
}

struct BridgeProcess {
    child: Child,
    stdin: ChildStdin,
    pending: PendingMap,
    _stdout_thread: JoinHandle<()>,
    _stderr_thread: JoinHandle<()>,
}

#[cfg(windows)]
fn configure_background_command(cmd: &mut Command) {
    use std::os::windows::process::CommandExt;
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    cmd.creation_flags(CREATE_NO_WINDOW);
}

#[cfg(not(windows))]
fn configure_background_command(_cmd: &mut Command) {}

fn ensure_bridge_process(app: &tauri::AppHandle, manager: &mut BridgeManager) -> Result<(), String> {
    let need_restart = match manager.process.as_mut() {
        Some(process) => process.child.try_wait().ok().flatten().is_some(),
        None => true,
    };
    if need_restart {
        manager.process = Some(spawn_bridge_process(app)?);
    }
    Ok(())
}

fn bridge_candidates(app: &tauri::AppHandle, filename: &str) -> Vec<PathBuf> {
    let mut candidates: Vec<PathBuf> = Vec::new();

    if let Ok(resource_dir) = app.path().resource_dir() {
        candidates.push(resource_dir.join(filename));
        candidates.push(resource_dir.join("_up_").join(filename));
    }

    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(exe_dir) = exe_path.parent() {
            candidates.push(exe_dir.join(filename));
            candidates.push(exe_dir.join("_up_").join(filename));
        }
    }

    candidates
}

fn resolve_bridge_executable(app: &tauri::AppHandle) -> Option<PathBuf> {
    for candidate in bridge_candidates(app, "bridge/bridge.exe") {
        if candidate.exists() {
            return Some(candidate);
        }
    }
    for candidate in bridge_candidates(app, "bridge.exe") {
        if candidate.exists() {
            return Some(candidate);
        }
    }
    None
}

fn resolve_bridge_script(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    if cfg!(debug_assertions) {
        let cwd = std::env::current_dir().map_err(|e| e.to_string())?;
        let script = cwd.join("tauri_bridge.py");
        if script.exists() {
            return Ok(script);
        }
        return Err(format!(
            "bridge script not found in debug mode: {}",
            script.display()
        ));
    }

    let candidates = bridge_candidates(app, "tauri_bridge.py");

    for candidate in &candidates {
        if candidate.exists() {
            return Ok(candidate.clone());
        }
    }

    let inspected = candidates
        .iter()
        .map(|p| p.display().to_string())
        .collect::<Vec<_>>()
        .join(", ");
    Err(format!("bridge script not found; checked: {inspected}"))
}

fn resolve_python_executable(app: &tauri::AppHandle) -> String {
    // Prefer bundled runtime for portable builds.
    for candidate in bridge_candidates(app, "python/python.exe") {
        if candidate.exists() {
            return candidate.display().to_string();
        }
    }
    // Fallback for local dev.
    "python".to_string()
}

fn fail_all_pending(pending: &PendingMap, message: String) {
    if let Ok(mut map) = pending.lock() {
        let channels: Vec<Sender<Result<BridgeResponse, String>>> =
            map.drain().map(|(_, tx)| tx).collect();
        for tx in channels {
            let _ = tx.send(Err(message.clone()));
        }
    }
}

fn spawn_stdout_reader(stdout: ChildStdout, pending: PendingMap) -> JoinHandle<()> {
    std::thread::spawn(move || {
        let mut reader = BufReader::new(stdout);
        let mut line = String::new();

        loop {
            line.clear();
            match reader.read_line(&mut line) {
                Ok(0) => {
                    fail_all_pending(&pending, "bridge closed unexpectedly".to_string());
                    break;
                }
                Ok(_) => {
                    let payload = line.trim();
                    if payload.is_empty() {
                        continue;
                    }
                    match serde_json::from_str::<BridgeResponse>(payload) {
                        Ok(resp) => {
                            if let Ok(mut map) = pending.lock() {
                                if let Some(tx) = map.remove(&resp.id) {
                                    let _ = tx.send(Ok(resp));
                                }
                            }
                        }
                        Err(err) => {
                            fail_all_pending(&pending, format!("bridge protocol error: {err}"));
                            break;
                        }
                    }
                }
                Err(err) => {
                    fail_all_pending(&pending, format!("bridge read failed: {err}"));
                    break;
                }
            }
        }
    })
}

fn spawn_stderr_reader(stderr: ChildStderr) -> JoinHandle<()> {
    std::thread::spawn(move || {
        let reader = BufReader::new(stderr);
        for line in reader.lines() {
            if let Ok(msg) = line {
                if !msg.trim().is_empty() {
                    eprintln!("[bridge] {msg}");
                }
            }
        }
    })
}

fn spawn_bridge_process(app: &tauri::AppHandle) -> Result<BridgeProcess, String> {
    let mut cmd = if let Some(bridge_exe) = resolve_bridge_executable(app) {
        let mut bridge_cmd = Command::new(bridge_exe.as_os_str());
        if let Some(parent) = bridge_exe.parent() {
            bridge_cmd.current_dir(parent);
        }
        bridge_cmd
    } else {
        let script_path = resolve_bridge_script(app)?;
        let script_dir = script_path
            .parent()
            .ok_or_else(|| "bridge script parent not found".to_string())?;
        let mut python_cmd = Command::new(resolve_python_executable(app));
        python_cmd.current_dir(script_dir).arg(script_path.as_os_str());
        python_cmd
    };

    configure_background_command(&mut cmd);

    let mut child = cmd
        .arg("--mode")
        .arg("server")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("failed to start bridge server: {e}"))?;

    let stdin = child
        .stdin
        .take()
        .ok_or_else(|| "bridge stdin is not available".to_string())?;
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| "bridge stdout is not available".to_string())?;
    let stderr = child
        .stderr
        .take()
        .ok_or_else(|| "bridge stderr is not available".to_string())?;

    let pending: PendingMap = Arc::new(Mutex::new(HashMap::new()));
    let stdout_thread = spawn_stdout_reader(stdout, pending.clone());
    let stderr_thread = spawn_stderr_reader(stderr);

    Ok(BridgeProcess {
        child,
        stdin,
        pending,
        _stdout_thread: stdout_thread,
        _stderr_thread: stderr_thread,
    })
}

fn run_bridge_oneshot(
    app: &tauri::AppHandle,
    mode: &str,
    input_path: &str,
    output_path: Option<&str>,
    threshold: i32,
    width: i32,
    height: i32,
    refine_method: &str,
    morph_kernel_size: i32,
    contour_expand: i32,
    bg_tolerance: i32,
    fast_preview: bool,
    preview_max_side: i32,
    preview_codec: &str,
    preview_quality: i32,
) -> Result<String, String> {
    let mut cmd = if let Some(bridge_exe) = resolve_bridge_executable(app) {
        let mut bridge_cmd = Command::new(bridge_exe.as_os_str());
        if let Some(parent) = bridge_exe.parent() {
            bridge_cmd.current_dir(parent);
        }
        bridge_cmd
    } else {
        let script_path = resolve_bridge_script(app)?;
        let script_dir = script_path
            .parent()
            .ok_or_else(|| "bridge script parent not found".to_string())?;

        let mut python_cmd = Command::new(resolve_python_executable(app));
        python_cmd.current_dir(script_dir).arg(script_path.as_os_str());
        python_cmd
    };

    cmd.arg("--mode")
        .arg(mode)
        .arg("--input")
        .arg(input_path)
        .arg("--threshold")
        .arg(threshold.to_string())
        .arg("--width")
        .arg(width.to_string())
        .arg("--height")
        .arg(height.to_string())
        .arg("--refine-method")
        .arg(refine_method)
        .arg("--morph-kernel-size")
        .arg(morph_kernel_size.to_string())
        .arg("--contour-expand")
        .arg(contour_expand.to_string())
        .arg("--bg-tolerance")
        .arg(bg_tolerance.to_string())
        .arg("--fast-preview")
        .arg(if fast_preview { "1" } else { "0" })
        .arg("--preview-max-side")
        .arg(preview_max_side.to_string())
        .arg("--preview-codec")
        .arg(preview_codec)
        .arg("--preview-quality")
        .arg(preview_quality.to_string());

    configure_background_command(&mut cmd);

    if let Some(out) = output_path {
        cmd.arg("--output").arg(out);
    }

    let output = cmd.output().map_err(|e| e.to_string())?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).to_string();
        return Err(format!("bridge failed: {stderr}"));
    }

    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    let parsed: BridgeResponse = serde_json::from_str(&stdout).map_err(|e| e.to_string())?;
    if !parsed.ok {
        return Err(parsed.error.unwrap_or_else(|| "unknown bridge error".to_string()));
    }
    parsed
        .preview
        .ok_or_else(|| "bridge response missing preview".to_string())
}

struct RequestOptions<'a> {
    mode: &'a str,
    input_path: &'a str,
    output_path: Option<&'a str>,
    threshold: i32,
    width: i32,
    height: i32,
    refine_method: &'a str,
    morph_kernel_size: i32,
    contour_expand: i32,
    bg_tolerance: i32,
    fast_preview: bool,
    preview_max_side: i32,
    preview_codec: &'a str,
    preview_quality: i32,
}

fn run_bridge_persistent(
    app: &tauri::AppHandle,
    state: &tauri::State<'_, BridgeState>,
    options: RequestOptions<'_>,
) -> Result<String, String> {
    let (request_id, rx, pending) = {
        let mut manager = state
            .manager
            .lock()
            .map_err(|_| "bridge manager lock poisoned".to_string())?;

        ensure_bridge_process(app, &mut manager)?;

        manager.request_seq += 1;
        let request_id = format!("req-{}", manager.request_seq);
        let request = BridgeRequest {
            id: request_id.clone(),
            mode: options.mode,
            input: options.input_path,
            output: options.output_path,
            threshold: options.threshold,
            width: options.width,
            height: options.height,
            refine_method: options.refine_method,
            morph_kernel_size: options.morph_kernel_size,
            contour_expand: options.contour_expand,
            bg_tolerance: options.bg_tolerance,
            fast_preview: options.fast_preview,
            preview_max_side: options.preview_max_side,
            preview_codec: options.preview_codec,
            preview_quality: options.preview_quality,
        };
        let payload = serde_json::to_string(&request).map_err(|e| e.to_string())?;
        let (tx, rx) = mpsc::channel::<Result<BridgeResponse, String>>();

        let process = manager
            .process
            .as_mut()
            .ok_or_else(|| "bridge process not available".to_string())?;
        let pending = process.pending.clone();
        if let Ok(mut map) = pending.lock() {
            map.insert(request_id.clone(), tx);
        }
        if let Err(err) = process.stdin.write_all(payload.as_bytes()) {
            if let Ok(mut map) = pending.lock() {
                map.remove(&request_id);
            }
            manager.process = None;
            return Err(format!("failed to write bridge request: {err}"));
        }
        if let Err(err) = process.stdin.write_all(b"\n") {
            if let Ok(mut map) = pending.lock() {
                map.remove(&request_id);
            }
            manager.process = None;
            return Err(format!("failed to flush bridge newline: {err}"));
        }
        if let Err(err) = process.stdin.flush() {
            if let Ok(mut map) = pending.lock() {
                map.remove(&request_id);
            }
            manager.process = None;
            return Err(format!("failed to flush bridge request: {err}"));
        }

        (request_id, rx, pending)
    };

    match rx.recv_timeout(Duration::from_millis(BRIDGE_TIMEOUT_MS)) {
        Ok(Ok(resp)) => {
            if !resp.ok {
                return Err(resp.error.unwrap_or_else(|| "unknown bridge error".to_string()));
            }
            resp.preview
                .ok_or_else(|| "bridge response missing preview".to_string())
        }
        Ok(Err(err)) => Err(err),
        Err(_) => {
            if let Ok(mut map) = pending.lock() {
                map.remove(&request_id);
            }
            let mut manager = state
                .manager
                .lock()
                .map_err(|_| "bridge manager lock poisoned".to_string())?;
            manager.process = None;
            Err(format!("bridge request timed out after {BRIDGE_TIMEOUT_MS}ms"))
        }
    }
}

#[tauri::command]
fn preview_image(
    app: tauri::AppHandle,
    state: tauri::State<'_, BridgeState>,
    input_path: String,
    threshold: i32,
    width: i32,
    height: i32,
    refine_method: String,
    morph_kernel_size: i32,
    contour_expand: i32,
    bg_tolerance: i32,
    fast_preview: Option<bool>,
    preview_max_side: Option<i32>,
    preview_codec: Option<String>,
    preview_quality: Option<i32>,
) -> Result<String, String> {
    let codec = preview_codec.unwrap_or_else(|| "jpeg".to_string());
    let request = RequestOptions {
        mode: "preview",
        input_path: &input_path,
        output_path: None,
        threshold,
        width,
        height,
        refine_method: &refine_method,
        morph_kernel_size,
        contour_expand,
        bg_tolerance,
        fast_preview: fast_preview.unwrap_or(true),
        preview_max_side: preview_max_side.unwrap_or(720),
        preview_codec: &codec,
        preview_quality: preview_quality.unwrap_or(85),
    };

    run_bridge_persistent(&app, &state, request).or_else(|_| {
        run_bridge_oneshot(
            &app,
            "preview",
            &input_path,
            None,
            threshold,
            width,
            height,
            &refine_method,
            morph_kernel_size,
            contour_expand,
            bg_tolerance,
            fast_preview.unwrap_or(true),
            preview_max_side.unwrap_or(720),
            &codec,
            preview_quality.unwrap_or(85),
        )
    })
}

#[tauri::command]
fn process_and_save(
    app: tauri::AppHandle,
    state: tauri::State<'_, BridgeState>,
    input_path: String,
    output_path: String,
    threshold: i32,
    width: i32,
    height: i32,
    refine_method: String,
    morph_kernel_size: i32,
    contour_expand: i32,
    bg_tolerance: i32,
) -> Result<String, String> {
    let request = RequestOptions {
        mode: "process",
        input_path: &input_path,
        output_path: Some(&output_path),
        threshold,
        width,
        height,
        refine_method: &refine_method,
        morph_kernel_size,
        contour_expand,
        bg_tolerance,
        fast_preview: false,
        preview_max_side: 0,
        preview_codec: "png",
        preview_quality: 100,
    };

    run_bridge_persistent(&app, &state, request).or_else(|_| {
        run_bridge_oneshot(
            &app,
            "process",
            &input_path,
            Some(&output_path),
            threshold,
            width,
            height,
            &refine_method,
            morph_kernel_size,
            contour_expand,
            bg_tolerance,
            false,
            0,
            "png",
            100,
        )
    })
}

pub fn run() {
    tauri::Builder::default()
        .manage(BridgeState::default())
        .setup(|app| {
            let app_handle = app.handle().clone();
            std::thread::spawn(move || {
                let state = app_handle.state::<BridgeState>();
                let manager_lock = state.manager.lock();
                if let Ok(mut manager) = manager_lock {
                    let _ = ensure_bridge_process(&app_handle, &mut manager);
                }
            });
            Ok(())
        })
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![preview_image, process_and_save])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
