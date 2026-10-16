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
    // 路径通过 argv 传递（sys.argv），避免拼进 Python 字符串字面量：
    // Windows 路径 C:\Users 的 \U 会触发 Unicode 转义 SyntaxError
    let start_cmd = "import sys; sys.path.insert(0, sys.argv[1]); from bingo_engine import start_game; start_game(sys.argv[2], sys.argv[3])";

    let mut cmd = Command::new(&python_path);
    cmd.arg("-u")
        .arg("-c")
        .arg(start_cmd)
        .arg(&engine_dir)
        .arg(&working_dir)
        .arg(target_arg)
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
        use std::io::{BufRead, BufReader};
        let reader = stdout;
        let mut buf_reader = BufReader::new(reader);
        let mut line = String::new();
        loop {
            line.clear();
            match buf_reader.read_line(&mut line) {
                Ok(0) => break,
                Ok(_) => {
                    if !line.is_empty() {
                        let _ = app_stdout.emit_to("main", "engine:stdout", SessionEvent { run_id: rid, data: line.clone() });
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
        use std::io::{BufRead, BufReader};
        let reader = stderr;
        let mut buf_reader = BufReader::new(reader);
        let mut line = String::new();
        loop {
            line.clear();
            match buf_reader.read_line(&mut line) {
                Ok(0) => break,
                Ok(_) => {
                    if !line.is_empty() {
                        let _ = app_stderr.emit_to("main", "engine:stderr", SessionEvent { run_id: rid, data: line.clone() });
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
            use std::process::Stdio;
            const CREATE_NO_WINDOW: u32 = 0x08000000;
            // 不等待 taskkill 完成，防止阻塞 mutex 导致 UI 卡死
            let _ = Command::new("taskkill")
                .args(["/F", "/T", "/PID", &pid.to_string()])
                .creation_flags(CREATE_NO_WINDOW)
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .spawn();
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

    // 包装脚本：覆盖 builtins.input 以优雅处理 EOFError（Windows 停止进程时 stdin 关闭）
    let script_content = std::fs::read_to_string(&script_path)
        .map_err(|e| format!("Failed to read script: {}", e))?;
    let wrapped_script = format!(
        "import builtins as _bi, sys as _sys, os as _os\n\
         _input_ref = _sys.stdin\n\
         _write_ref = _sys.stdout.write\n\
         _flush_ref = _sys.stdout.flush\n\
         _stdin_closed = False\n\
         def _safe_input(prompt=''):\n\
         \x20   global _stdin_closed\n\
         \x20   if _stdin_closed:\n\
         \x20       \x20   raise SystemExit\n\
         \x20   _write_ref(str(prompt) + '__BINGO_WAITING_INPUT__\\n')\n\
         \x20   _flush_ref()\n\
         \x20   try:\n\
         \x20       \x20   line = _input_ref.readline()\n\
         \x20       \x20   if not line:\n\
         \x20       \x20       \x20   _stdin_closed = True\n\
         \x20       \x20       \x20   raise SystemExit\n\
         \x20       \x20   return line.rstrip('\\n')\n\
         \x20   except (EOFError, OSError):\n\
         \x20       \x20   _stdin_closed = True\n\
         \x20       \x20   raise SystemExit\n\
         _bi.input = _safe_input\n\
         {}\n\
         # IDE 收尾（turtle）：\n\
         # 1) 窗口关闭按钮 → 立即结束整个 Python 进程，避免窗口已销毁但进程仍在运行导致假死\n\
         # 2) 用 Tk 的 after() 调度器保活（线程安全、跨平台一致），学生未写 turtle.done() 时窗口不闪退\n\
         try:\n\
         \x20   _tm = _sys.modules.get('turtle')\n\
         \x20   _scr_cls = getattr(_tm, 'Turtle', None)\n\
         \x20   _tsc = getattr(_scr_cls, '_screen', None) if _scr_cls else None\n\
         \x20   if _tsc is not None:\n\
         \x20       \x20   _root = _tsc._root\n\
         \x20       \x20   _root.winfo_exists()\n\
         \x20       \x20   def _ide_close(*_a):\n\
         \x20       \x20   \x20   _os._exit(0)\n\
         \x20       \x20   _root.protocol('WM_DELETE_WINDOW', _ide_close)\n\
         \x20       \x20   def _ide_keepalive():\n\
         \x20       \x20   \x20   try:\n\
         \x20       \x20   \x20   \x20   if _root.winfo_exists():\n\
         \x20       \x20   \x20   \x20   \x20   _root.after(200, _ide_keepalive)\n\
         \x20       \x20   \x20   \x20   else:\n\
         \x20       \x20   \x20   \x20   \x20   _os._exit(0)\n\
         \x20       \x20   \x20   except Exception:\n\
         \x20       \x20   \x20   \x20   _os._exit(0)\n\
         \x20       \x20   _root.after(200, _ide_keepalive)\n\
         \x20       \x20   _tm.mainloop()\n\
         except Exception:\n\
         \x20   pass\n",
        script_content
    );
    let wrapped_path = format!("{}.wrapped.py", script_path);
    std::fs::write(&wrapped_path, &wrapped_script)
        .map_err(|e| format!("Failed to write wrapped script: {}", e))?;

    let mut cmd = Command::new(&python_path);
    cmd.arg("-u")
        .arg(&wrapped_path)
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
        use std::io::{BufRead, BufReader};
        let reader = stdout;
        let mut buf_reader = BufReader::new(reader);
        let mut line = String::new();
        loop {
            line.clear();
            match buf_reader.read_line(&mut line) {
                Ok(0) => break,
                Ok(_) => {
                    if !line.is_empty() {
                        let _ = app_stdout.emit_to("main", "engine:stdout", SessionEvent { run_id: rid, data: line.clone() });
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
        use std::io::{BufRead, BufReader};
        let reader = stderr;
        let mut buf_reader = BufReader::new(reader);
        let mut line = String::new();
        loop {
            line.clear();
            match buf_reader.read_line(&mut line) {
                Ok(0) => break,
                Ok(_) => {
                    if !line.is_empty() {
                        let _ = app_stderr.emit_to("main", "engine:stderr", SessionEvent { run_id: rid, data: line.clone() });
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
