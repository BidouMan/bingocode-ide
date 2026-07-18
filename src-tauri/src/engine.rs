use std::io::Write;
use std::process::{ChildStdin, Command, Stdio};
use tauri::{AppHandle, Emitter};
use serde::Serialize;

use crate::EngineState;

pub struct RunningProcess {
    pub stdin: Option<ChildStdin>,
    pub pid: u32,
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

    let mut cmd = Command::new(&python_path);
    cmd.arg("-u")
        .arg("-c")
        .arg(&start_cmd)
        .current_dir(&working_dir)
        .env("PYTHONPATH", &engine_dir)
        .env("PYTHONUNBUFFERED", "1")
        .env("PYTHONIOENCODING", "utf-8")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .stdin(Stdio::piped());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    let mut child = cmd.spawn()
        .map_err(|e| format!("Failed to spawn Python process: {}", e))?;

    let pid = child.id();
    let stdin = child.stdin.take();
    let stdout = child.stdout.take().ok_or("Failed to capture stdout")?;
    let stderr = child.stderr.take().ok_or("Failed to capture stderr")?;

    // stdout 读取线程
    let app_stdout = app.clone();
    let rid = run_id;
    std::thread::spawn(move || {
        use std::io::Read;
        let mut reader = stdout;
        let mut buf = [0u8; 4096];
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

    // stderr 读取线程
    let app_stderr = app.clone();
    let rid = run_id;
    std::thread::spawn(move || {
        use std::io::Read;
        let mut reader = stderr;
        let mut buf = [0u8; 4096];
        loop {
            match reader.read(&mut buf) {
                Ok(0) => break,
                Ok(n) => {
                    let data = String::from_utf8_lossy(&buf[..n]).to_string();
                    if !data.is_empty() {
                        let _ = app_stderr.emit_to("main", "engine:stderr", SessionEvent { run_id: rid, data });
                    }
                }
                Err(_) => break,
            }
        }
    });

    // 保存 stdin 和 pid 供 send_stdin/stop_script 使用
    *process_guard = Some(RunningProcess { stdin, pid });
    drop(process_guard);

    // 进程等待线程：直接用 child.wait()，不再轮询 tasklist
    let app_finish = app.clone();
    let rid = run_id;
    std::thread::spawn(move || {
        let _ = child.wait();  // 阻塞直到进程退出，跨平台通用
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
    if let Some(proc) = process.take() {
        let pid = proc.pid;

        #[cfg(unix)]
        unsafe {
            libc::kill(pid as i32, libc::SIGTERM);
        }

        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x08000000;
            let _ = Command::new("taskkill")
                .args(["/F", "/T", "/PID", &pid.to_string()])
                .creation_flags(CREATE_NO_WINDOW)
                .output();
        }
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
        if let Some(ref mut stdin) = proc.stdin {
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
        if let Some(ref mut stdin) = proc.stdin {
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

    let mut cmd = Command::new(&python_path);
    cmd.arg("-u")
        .arg(&script_path)
        .current_dir(&working_dir)
        .env("PYTHONUNBUFFERED", "1")
        .env("PYTHONIOENCODING", "utf-8")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .stdin(Stdio::piped());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    let mut child = cmd.spawn()
        .map_err(|e| format!("Failed to spawn Python process: {}", e))?;

    let pid = child.id();
    let stdin = child.stdin.take();
    let stdout = child.stdout.take().ok_or("Failed to capture stdout")?;
    let stderr = child.stderr.take().ok_or("Failed to capture stderr")?;

    // stdout 读取线程
    let app_stdout = app.clone();
    let rid = run_id;
    std::thread::spawn(move || {
        use std::io::Read;
        let mut reader = stdout;
        let mut buf = [0u8; 4096];
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

    // stderr 读取线程
    let app_stderr = app.clone();
    let rid = run_id;
    std::thread::spawn(move || {
        use std::io::Read;
        let mut reader = stderr;
        let mut buf = [0u8; 4096];
        loop {
            match reader.read(&mut buf) {
                Ok(0) => break,
                Ok(n) => {
                    let data = String::from_utf8_lossy(&buf[..n]).to_string();
                    if !data.is_empty() {
                        let _ = app_stderr.emit_to("main", "engine:stderr", SessionEvent { run_id: rid, data });
                    }
                }
                Err(_) => break,
            }
        }
    });

    // 保存 stdin 和 pid 供 send_stdin/stop_script 使用
    *process_guard = Some(RunningProcess { stdin, pid });
    drop(process_guard);

    // 进程等待线程：直接用 child.wait()，不再轮询 tasklist
    let app_finish = app.clone();
    let rid = run_id;
    std::thread::spawn(move || {
        let _ = child.wait();  // 阻塞直到进程退出，跨平台通用
        let _ = app_finish.emit_to("main", "engine:finished", SessionEnd { run_id: rid });
    });

    Ok(())
}
