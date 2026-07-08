use std::io::{BufReader, Write};
use std::process::{Child, Command, Stdio};
use tauri::{AppHandle, Emitter};

use crate::EngineState;

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

    let app_stdout = app.clone();
    std::thread::spawn(move || {
        use std::io::BufRead;
        let mut reader = BufReader::new(stdout);
        let mut line = String::new();
        loop {
            line.clear();
            match reader.read_line(&mut line) {
                Ok(0) => break,
                Ok(_) => {
                    let trimmed = line.trim_end_matches('\n').trim_end_matches('\r');
                    if !trimmed.is_empty() {
                        let _ = app_stdout.emit_to("main", "engine:stdout", line.clone());
                    }
                }
                Err(_) => break,
            }
        }
        let _ = app_stdout.emit_to("main", "engine:stdout:end", ());
    });

    let app_stderr = app.clone();
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
                        let _ = app_stderr.emit_to("main", "engine:stderr", line.clone());
                    }
                }
                Err(_) => break,
            }
        }
    });

    *process_guard = Some(RunningProcess { child });
    drop(process_guard);

    let app_finish = app.clone();
    std::thread::spawn(move || {
        unsafe {
            libc::waitpid(pid as i32, std::ptr::null_mut(), 0);
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
