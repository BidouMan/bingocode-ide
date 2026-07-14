use std::io::{Read, Write};
use tauri::{AppHandle, Emitter};
use portable_pty::{CommandBuilder, NativePtySystem, PtySize, PtySystem};

use crate::ShellState;

#[tauri::command]
pub fn start_shell(
    app: AppHandle,
    state: tauri::State<'_, ShellState>,
    working_dir: String,
) -> Result<(), String> {
    let mut shell_guard = state.pty.lock().map_err(|e| e.to_string())?;

    if shell_guard.is_some() {
        stop_shell_process(&mut shell_guard)?;
    }

    let pty_system = NativePtySystem::default();

    let size = PtySize {
        rows: 24,
        cols: 80,
        pixel_width: 0,
        pixel_height: 0,
    };

    let pair = pty_system
        .openpty(size)
        .map_err(|e| format!("Failed to open PTY: {}", e))?;

    // 选择用户默认 shell，加 --norc --noprofile 跳过用户美化配置
    #[cfg(target_os = "macos")]
    let shell = std::env::var("SHELL").unwrap_or_else(|_| "/bin/zsh".to_string());
    #[cfg(target_os = "windows")]
    let shell = "cmd.exe".to_string();
    #[cfg(not(any(target_os = "macos", target_os = "windows")))]
    let shell = std::env::var("SHELL").unwrap_or_else(|_| "/bin/bash".to_string());

    let mut cmd = CommandBuilder::new(&shell);
    // 跳过用户 .zshrc / .bashrc 等美化配置，保持统一的干净终端
    #[cfg(not(target_os = "windows"))]
    {
        let shell_name = std::path::Path::new(&shell)
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("");
        if shell_name == "zsh" {
            // macOS /bin/zsh 用 -f 跳过所有启动文件
            cmd.arg("-f");
        } else if shell_name == "bash" {
            cmd.arg("--norc");
            cmd.arg("--noprofile");
        }
    }
    cmd.cwd(&working_dir);

    // 设置终端类型为最基础的 xterm，避免触发美化插件
    cmd.env("TERM", "dumb");
    cmd.env("NO_COLOR", "1");
    cmd.env("FORCE_COLOR", "0");
    // 设置 UTF-8 编码，避免中文路径乱码
    cmd.env("LANG", "en_US.UTF-8");
    cmd.env("LC_ALL", "en_US.UTF-8");
    // 清空提示符，保持终端输出纯净
    cmd.env("PS1", "");
    cmd.env("PS2", "");
    cmd.env_remove("PROMPT_COMMAND");

    let child = pair
        .slave
        .spawn_command(cmd)
        .map_err(|e| format!("Failed to spawn shell: {}", e))?;

    let mut reader = pair
        .master
        .try_clone_reader()
        .map_err(|e| format!("Failed to clone reader: {}", e))?;

    let writer = pair
        .master
        .take_writer()
        .map_err(|e| format!("Failed to take writer: {}", e))?;

    // 后台线程读取 PTY 输出
    let app_clone = app.clone();
    std::thread::spawn(move || {
        let mut buf = [0u8; 8192];
        loop {
            match reader.read(&mut buf) {
                Ok(0) => break,
                Ok(n) => {
                    let data = String::from_utf8_lossy(&buf[..n]).to_string();
                    if !data.is_empty() {
                        let _ = app_clone.emit_to("main", "shell:stdout", data);
                    }
                }
                Err(_) => break,
            }
        }
        let _ = app_clone.emit_to("main", "shell:exited", ());
    });

    *shell_guard = Some(crate::RunningShell {
        child,
        writer: Some(writer),
        pair: Some(pair),
    });

    Ok(())
}

#[tauri::command]
pub fn send_shell_input(
    state: tauri::State<'_, ShellState>,
    data: String,
) -> Result<(), String> {
    let mut shell_guard = state.pty.lock().map_err(|e| e.to_string())?;

    if let Some(ref mut shell) = *shell_guard {
        if let Some(ref mut writer) = shell.writer {
            let _ = writer.write_all(data.as_bytes());
            let _ = writer.flush();
        }
    }

    Ok(())
}

#[tauri::command]
pub fn resize_shell(
    state: tauri::State<'_, ShellState>,
    cols: u16,
    rows: u16,
) -> Result<(), String> {
    let mut shell_guard = state.pty.lock().map_err(|e| e.to_string())?;

    if let Some(ref mut shell) = *shell_guard {
        if let Some(ref pair) = shell.pair {
            let size = PtySize {
                rows,
                cols,
                pixel_width: 0,
                pixel_height: 0,
            };
            let _ = pair.master.resize(size);
        }
    }

    Ok(())
}

#[tauri::command]
pub fn stop_shell(
    state: tauri::State<'_, ShellState>,
) -> Result<(), String> {
    let mut shell_guard = state.pty.lock().map_err(|e| e.to_string())?;
    stop_shell_process(&mut shell_guard)
}

fn stop_shell_process(shell: &mut Option<crate::RunningShell>) -> Result<(), String> {
    if let Some(mut s) = shell.take() {
        drop(s.writer.take());
        let _ = s.child.kill();
        let _ = s.child.wait();
    }
    Ok(())
}
