use std::io::{BufReader, Read, Write};
use std::process::{Child, Command, Stdio};
use tauri::{AppHandle, Emitter};

use crate::EngineState;

/// 读取 stdout（字节级，不等到换行符，解决 input() 提示不显示的问题）
fn spawn_stdout_reader(
    stdout: std::process::ChildStdout,
    app: AppHandle,
    event: &'static str,
    end_event: &'static str,
) {
    std::thread::spawn(move || {
        let mut reader = BufReader::new(stdout);
        let mut buf = [0u8; 4096];
        let mut partial = String::new();
        loop {
            match reader.read(&mut buf) {
                Ok(0) => break,
                Ok(n) => {
                    let chunk = String::from_utf8_lossy(&buf[..n]);
                    partial.push_str(&chunk);
                    // 把完整行（含换行符）发送出去
                    while let Some(pos) = partial.find('\n') {
                        let line = partial[..=pos].to_string();
                        let trimmed = line.trim_end_matches('\n').trim_end_matches('\r');
                        if !trimmed.is_empty() {
                            let _ = app.emit_to("main", event, line.clone());
                        }
                        partial.drain(..=pos);
                    }
                    // 剩余的半行数据（如 input() 提示文字）立即发送，不等换行
                    if !partial.is_empty() {
                        let _ = app.emit_to("main", event, partial.clone());
                        partial.clear();
                    }
                }
                Err(_) => break,
            }
        }
        // 进程退出，冲刷剩余数据
        if !partial.is_empty() {
            let _ = app.emit_to("main", event, partial.clone());
        }
        let _ = app.emit_to("main", end_event, ());
    });
}

/// 读取 stderr（行级即可，报错信息一般自带换行）
fn spawn_stderr_reader(stderr: std::process::ChildStderr, app: AppHandle) {
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
                        let _ = app.emit_to("main", "engine:stderr", line.clone());
                    }
                }
                Err(_) => break,
            }
        }
    });
}

pub struct RunningProcess {
    pub child: Child,
}

#[tauri::command]
pub fn run_script(
    app: AppHandle,
    state: tauri::State<'_, EngineState>,
    working_dir: String,
    python_path: String,
    engine_dir: String,
) -> Result<(), String> {
    let mut process_guard = state.process.lock().map_err(|e| e.to_string())?;

    if process_guard.is_some() {
        stop_script_process(&mut process_guard)?;
    }

    let start_cmd = format!(
        "import sys; sys.path.insert(0, '{}'); from bingo_engine import start_game; start_game('{}')",
        engine_dir, working_dir
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

    spawn_stdout_reader(stdout, app.clone(), "engine:stdout", "engine:stdout:end");
    spawn_stderr_reader(stderr, app.clone());

    *process_guard = Some(RunningProcess { child });
    drop(process_guard);

    let app_finish = app.clone();
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
        let _ = app_finish.emit_to("main", "engine:finished", ());
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

/// 代码模式：异步运行 Python 脚本文件
#[tauri::command]
pub fn run_script_file(
    app: AppHandle,
    state: tauri::State<'_, EngineState>,
    working_dir: String,
    python_path: String,
    script_path: String,
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

    let pid = child.id();

    let stdout = child.stdout.take().ok_or("Failed to capture stdout")?;
    let stderr = child.stderr.take().ok_or("Failed to capture stderr")?;

    spawn_stdout_reader(stdout, app.clone(), "engine:stdout", "engine:stdout:end");
    spawn_stderr_reader(stderr, app.clone());

    *process_guard = Some(RunningProcess { child });
    drop(process_guard);

    let app_finish = app.clone();
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
        let _ = app_finish.emit_to("main", "engine:finished", ());
    });

    Ok(())
}
