use std::io::{BufRead, BufReader, Write};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::{AppHandle, Emitter, Manager};

use crate::EngineState;

pub struct RunningProcess {
    pub child: Child,
}

#[tauri::command]
pub fn run_script(
    app: AppHandle,
    state: tauri::State<'_, EngineState>,
    script_path: String,
    working_dir: String,
    python_path: String,
    engine_dir: String,
) -> Result<(), String> {
    let mut process_guard = state.process.lock().map_err(|e| e.to_string())?;

    if process_guard.is_some() {
        stop_script_process(&mut process_guard)?;
    }

    let mut child = Command::new(&python_path)
        .arg("-u")
        .arg(&script_path)
        .current_dir(&working_dir)
        .env("PYTHONPATH", &engine_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .stdin(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to spawn Python process: {}", e))?;

    let stdout = child.stdout.take().ok_or("Failed to capture stdout")?;
    let stderr = child.stderr.take().ok_or("Failed to capture stderr")?;

    let app_clone = app.clone();
    std::thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines() {
            match line {
                Ok(line) => {
                    let _ = app_clone.emit("engine:stdout", line);
                }
                Err(_) => break,
            }
        }
        let _ = app_clone.emit("engine:stdout:end", ());
    });

    let app_clone = app.clone();
    std::thread::spawn(move || {
        let reader = BufReader::new(stderr);
        for line in reader.lines() {
            match line {
                Ok(line) => {
                    let _ = app_clone.emit("engine:stderr", line);
                }
                Err(_) => break,
            }
        }
    });

    *process_guard = Some(RunningProcess { child });

    let app_clone = app.clone();
    let state_ptr = &*state as *const EngineState;
    std::thread::spawn(move || {
        let pid;
        {
            if let Ok(mut guard) = state_ptr.lock() {
                pid = guard.as_ref().map(|p| p.child.id());
            } else {
                return;
            }
        }

        if let Some(pid) = pid {
            unsafe {
                libc::kill(pid as i32, libc::SIGTERM);
            }
        }

        {
            if let Ok(mut guard) = state_ptr.lock() {
                if let Some(mut proc) = guard.take() {
                    let _ = proc.child.wait();
                }
            }
        }

        let _ = app_clone.emit("engine:finished", ());
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
