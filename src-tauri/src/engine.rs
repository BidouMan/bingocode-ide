use std::io::{BufReader, Write};
use std::process::{Child, Command, Stdio};
use tauri::{AppHandle, Emitter};
use serde::Serialize;

use crate::EngineState;

pub struct RunningProcess {
    pub child: Child,
}

/// 带会话 ID 的事件载荷，用于前端精确过滤新旧进程事件
#[derive(Clone, Serialize)]
struct SessionEvent<T: Serialize> {
    run_id: u32,
    data: T,
}

#[derive(Clone, Serialize)]
struct SessionEnd {
    run_id: u32,
}

#[tauri::command]
pub fn run_script(
    app: AppHandle,
    state: tauri::State<'_, EngineState>,
    working_dir: String,
    python_path: String,
    engine_dir: String,
    script_path: Option<String>,
    run_id: u32,
) -> Result<(), String> {
    let mut process_guard = state.process.lock().map_err(|e| e.to_string())?;

    if process_guard.is_some() {
        stop_script_process(&mut process_guard)?;
    }

    let target_arg = script_path.as_deref().unwrap_or("");
    let start_cmd = format!(
        "import sys; sys.path.insert(0, '{}'); from bingo_engine import start_game; start_game('{}', '{}')",
        engine_dir, working_dir, target_arg
    );

    let mut child = Command::new(&python_path)
        .arg("-u")
        .arg("-c")
        .arg(&start_cmd)
        .current_dir(&working_dir)
        .env("PYTHONPATH", &engine_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .stdin(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to spawn Python process: {}", e))?;

    let pid = child.id();

    let stdout = child.stdout.take().ok_or("Failed to capture stdout")?;
    let stderr = child.stderr.take().ok_or("Failed to capture stderr")?;

    let app_stdout = app.clone();
    let rid = run_id;
    std::thread::spawn(move || {
        use std::io::BufRead;
        let mut reader = BufReader::new(stdout);
        let mut line = String::new();
        let mut batch = String::new();
        let mut last_flush = std::time::Instant::now();
        loop {
            line.clear();
            match reader.read_line(&mut line) {
                Ok(0) => {
                    if !batch.is_empty() {
                        let _ = app_stdout.emit_to("main", "engine:stdout", SessionEvent { run_id: rid, data: batch.clone() });
                        batch.clear();
                    }
                    break;
                }
                Ok(_) => {
                    batch.push_str(&line);
                    if last_flush.elapsed() >= std::time::Duration::from_millis(16) {
                        if !batch.is_empty() {
                            let _ = app_stdout.emit_to("main", "engine:stdout", SessionEvent { run_id: rid, data: batch.clone() });
                            batch.clear();
                        }
                        last_flush = std::time::Instant::now();
                    }
                }
                Err(_) => break,
            }
        }
        let _ = app_stdout.emit_to("main", "engine:stdout:end", SessionEnd { run_id: rid });
    });

    let app_stderr = app.clone();
    let rid = run_id;
    std::thread::spawn(move || {
        use std::io::BufRead;
        let mut reader = BufReader::new(stderr);
        let mut line = String::new();
        loop {
            line.clear();
            match reader.read_line(&mut line) {
                Ok(0) => break,
                Ok(_) => {
                    let trimmed = line.trim_end_matches('\n').trim_end_matches('\r');
                    if !trimmed.is_empty() {
                        let _ = app_stderr.emit_to("main", "engine:stderr", SessionEvent { run_id: rid, data: line.clone() });
                    }
                }
                Err(_) => break,
            }
        }
    });

    *process_guard = Some(RunningProcess { child });
    drop(process_guard);

    let app_finish = app.clone();
    let rid = run_id;
    std::thread::spawn(move || {
        #[cfg(unix)]
        unsafe {
            libc::waitpid(pid as i32, std::ptr::null_mut(), 0);
        }
        #[cfg(windows)]
        {
            let pid_str = pid.to_string();
            loop {
                let alive = std::process::Command::new("tasklist")
                    .args(["/FI", &format!("PID eq {}", pid_str), "/NH"])
                    .output()
                    .ok()
                    .and_then(|o| {
                        let s = String::from_utf8_lossy(&o.stdout);
                        if s.contains("No tasks") || s.contains("ERROR") {
                            Some(false)
                        } else {
                            Some(true)
                        }
                    })
                    .unwrap_or(false);
                if !alive {
                    break;
                }
                std::thread::sleep(std::time::Duration::from_millis(200));
            }
        }
        let _ = app_finish.emit_to("main", "engine:finished", SessionEnd { run_id: rid });
    });

    Ok(())
}

#[tauri::command]
pub fn stop_script(
    state: tauri::State<'_, EngineState>,
) -> Result<(), String> {
    let mut process_guard = state.process.lock().map_err(|e| e.to_string())?;
    stop_script_process(&mut process_guard)
}

fn stop_script_process(process: &mut Option<RunningProcess>) -> Result<(), String> {
    if let Some(mut proc) = process.take() {
        let pid = proc.child.id();

        #[cfg(unix)]
        unsafe {
            libc::kill(pid as i32, libc::SIGTERM);
        }

        #[cfg(windows)]
        {
            let _ = Command::new("taskkill")
                .args(["/F", "/T", "/PID", &pid.to_string()])
                .output();
        }

        let _ = proc.child.wait();
    }
    Ok(())
}

#[tauri::command]
pub fn send_stdin(
    state: tauri::State<'_, EngineState>,
    data: String,
) -> Result<(), String> {
    let mut process_guard = state.process.lock().map_err(|e| e.to_string())?;

    if let Some(proc) = process_guard.as_mut() {
        if let Some(ref mut stdin) = proc.child.stdin {
            let _ = stdin.write_all(format!("{}\n", data).as_bytes());
            let _ = stdin.flush();
        }
    }

    Ok(())
}

/// 代码模式：逐字符发送输入，不追加换行
#[tauri::command]
pub fn send_stdin_data(
    state: tauri::State<'_, EngineState>,
    data: String,
) -> Result<(), String> {
    let mut process_guard = state.process.lock().map_err(|e| e.to_string())?;

    if let Some(proc) = process_guard.as_mut() {
        if let Some(ref mut stdin) = proc.child.stdin {
            let _ = stdin.write_all(data.as_bytes());
            let _ = stdin.flush();
        }
    }

    Ok(())
}

/// 代码模式：异步运行 Python 脚本文件
#[tauri::command]
pub fn run_script_file(
    app: AppHandle,
    state: tauri::State<'_, EngineState>,
    working_dir: String,
    python_path: String,
    script_path: String,
    run_id: u32,
) -> Result<(), String> {
    let mut process_guard = state.process.lock().map_err(|e| e.to_string())?;

    if process_guard.is_some() {
        stop_script_process(&mut process_guard)?;
    }

    let mut child = Command::new(&python_path)
        .arg("-u")
        .arg(&script_path)
        .current_dir(&working_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .stdin(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to spawn Python process: {}", e))?;

    let stdout = child.stdout.take().ok_or("Failed to capture stdout")?;
    let stderr = child.stderr.take().ok_or("Failed to capture stderr")?;
    let pid = child.id();

    let app_stdout = app.clone();
    let rid = run_id;
    std::thread::spawn(move || {
        use std::io::Read;
        let mut reader = stdout;
        let mut buf = [0u8; 4096];
        // 代码模式：每次 read 返回数据后立即发送，不做节流
        // input() 的 prompt 不带 \n，必须立即发送否则会被卡在 batch 中
        // 高频输出的限流由前端 RAF 缓冲处理
        loop {
            match reader.read(&mut buf) {
                Ok(0) => break,
                Ok(n) => {
                    let data = String::from_utf8_lossy(&buf[..n]).to_string();
                    if !data.is_empty() {
                        let _ = app_stdout.emit_to("main", "engine:stdout", SessionEvent { run_id: rid, data });
                    }
                }
                Err(_) => break,
            }
        }
        let _ = app_stdout.emit_to("main", "engine:stdout:end", SessionEnd { run_id: rid });
    });

    let app_stderr = app.clone();
    let rid = run_id;
    std::thread::spawn(move || {
        use std::io::BufRead;
        let mut reader = BufReader::new(stderr);
        let mut line = String::new();
        loop {
            line.clear();
            match reader.read_line(&mut line) {
                Ok(0) => break,
                Ok(_) => {
                    let trimmed = line.trim_end_matches('\n').trim_end_matches('\r');
                    if !trimmed.is_empty() {
                        let _ = app_stderr.emit_to("main", "engine:stderr", SessionEvent { run_id: rid, data: line.clone() });
                    }
                }
                Err(_) => break,
            }
        }
    });

    *process_guard = Some(RunningProcess { child });
    drop(process_guard);

    let app_finish = app.clone();
    let rid = run_id;
    std::thread::spawn(move || {
        #[cfg(unix)]
        unsafe {
            libc::waitpid(pid as i32, std::ptr::null_mut(), 0);
        }
        #[cfg(windows)]
        {
            let pid_str = pid.to_string();
            loop {
                let alive = std::process::Command::new("tasklist")
                    .args(["/FI", &format!("PID eq {}", pid_str), "/NH"])
                    .output()
                    .ok()
                    .and_then(|o| {
                        let s = String::from_utf8_lossy(&o.stdout);
                        if s.contains("No tasks") || s.contains("ERROR") {
                            Some(false)
                        } else {
                            Some(true)
                        }
                    })
                    .unwrap_or(false);
                if !alive {
                    break;
                }
                std::thread::sleep(std::time::Duration::from_millis(200));
            }
        }
        let _ = app_finish.emit_to("main", "engine:finished", SessionEnd { run_id: rid });
    });

    Ok(())
}
