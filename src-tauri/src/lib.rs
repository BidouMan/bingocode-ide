use std::io::Write;
use std::path::PathBuf;
use std::process::Command;
use std::sync::Mutex;

use serde::{Deserialize, Serialize};
use tauri::{LogicalSize, Manager, RunEvent, WindowEvent};

mod engine;
mod fs_ops;
mod media;
mod pack;
mod pip;
mod project;
mod python_env;
mod shell;

/// 上次退出时的窗口尺寸（逻辑像素，跨不同缩放比例的显示器一致）+ 是否最大化
#[derive(Clone, Copy, Default, Serialize, Deserialize)]
struct WindowGeometry {
    width: f64,
    height: f64,
    maximized: bool,
}

/// 窗口尺寸记忆（内存态，退出时落盘）
#[derive(Default)]
pub struct WindowSizeState {
    geometry: Mutex<Option<WindowGeometry>>,
}

fn window_size_path(app: &tauri::AppHandle) -> Option<PathBuf> {
    app.path()
        .app_config_dir()
        .ok()
        .map(|dir| dir.join("window-size.json"))
}

/// 窗口尺寸变化时记到内存（最大值化只记标记，保留退出最大化后的普通尺寸）
fn record_window_size(app: &tauri::AppHandle) {
    let Some(win) = app.get_webview_window("main") else {
        return;
    };
    let maximized = win.is_maximized().unwrap_or(false);
    let state = app.state::<WindowSizeState>();
    let Ok(mut guard) = state.geometry.lock() else {
        return;
    };
    if maximized {
        let prev = guard.unwrap_or_default();
        *guard = Some(WindowGeometry {
            maximized: true,
            ..prev
        });
        return;
    }
    let (Ok(size), Ok(scale)) = (win.inner_size(), win.scale_factor()) else {
        return;
    };
    let logical = size.to_logical::<f64>(scale);
    if logical.width <= 0.0 || logical.height <= 0.0 {
        return;
    }
    *guard = Some(WindowGeometry {
        width: logical.width,
        height: logical.height,
        maximized: false,
    });
}

/// 把内存里的窗口尺寸写入配置文件（下次启动恢复）
fn save_window_size(app: &tauri::AppHandle) {
    let Some(path) = window_size_path(app) else {
        return;
    };
    let state = app.state::<WindowSizeState>();
    let Ok(guard) = state.geometry.lock() else {
        return;
    };
    let Some(geometry) = *guard else {
        return;
    };
    if let Some(dir) = path.parent() {
        let _ = std::fs::create_dir_all(dir);
    }
    if let Ok(json) = serde_json::to_string(&geometry) {
        let _ = std::fs::write(path, json);
    }
}

/// 启动时按上次退出状态恢复窗口尺寸（没有记录则保持配置默认 1000×650）
fn restore_window_size(app: &tauri::AppHandle) {
    let Some(win) = app.get_webview_window("main") else {
        return;
    };
    let Some(path) = window_size_path(app) else {
        return;
    };
    let Ok(raw) = std::fs::read_to_string(path) else {
        return;
    };
    let Ok(geometry) = serde_json::from_str::<WindowGeometry>(&raw) else {
        return;
    };
    // 先把记录写回内存：启动后一直保持最大化时，退出也能保留普通尺寸
    if let Ok(mut guard) = app.state::<WindowSizeState>().geometry.lock() {
        *guard = Some(geometry);
    }
    if geometry.maximized {
        let _ = win.maximize();
    } else if geometry.width > 0.0 && geometry.height > 0.0 {
        let _ = win.set_size(LogicalSize::new(geometry.width, geometry.height));
        let _ = win.center();
    }
}

/// 创建 Command 时自动添加 CREATE_NO_WINDOW 标志（Windows）
/// 防止任何子进程弹出系统终端窗口
#[allow(unused_mut)]
pub(crate) fn hidden_command<S: AsRef<std::ffi::OsStr>>(program: S) -> Command {
    let mut cmd = Command::new(program);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    cmd
}

pub struct EngineState {
    pub process: Mutex<Option<engine::RunningProcess>>,
}

pub struct RunningShell {
    pub child: Box<dyn portable_pty::Child + Send>,
    pub writer: Option<Box<dyn Write + Send>>,
    pub pair: Option<portable_pty::PtyPair>,
}

pub struct ShellState {
    pub pty: Mutex<Option<RunningShell>>,
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(EngineState {
            process: Mutex::new(None),
        })
        .manage(ShellState {
            pty: Mutex::new(None),
        })
        .manage(WindowSizeState::default())
        .setup(|app| {
            // 恢复上次退出时的窗口大小（首次启动保持配置默认尺寸）
            restore_window_size(app.handle());
            if let Some(win) = app.get_webview_window("main") {
                let handle = app.handle().clone();
                win.on_window_event(move |event| match event {
                    WindowEvent::Resized(_) | WindowEvent::ScaleFactorChanged { .. } => {
                        record_window_size(&handle)
                    }
                    WindowEvent::CloseRequested { .. } | WindowEvent::Destroyed => {
                        save_window_size(&handle)
                    }
                    _ => {}
                });
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            // 文件系统
            fs_ops::read_file,
            fs_ops::write_file,
            fs_ops::read_binary,
            fs_ops::write_binary,
            fs_ops::list_dir,
            fs_ops::create_dir,
            fs_ops::delete_path,
            fs_ops::path_exists,
            fs_ops::open_file_in_browser,
            fs_ops::rename_path,
            fs_ops::copy_file,
            // 项目与素材
            project::save_temp_script,
            project::cleanup_temp_script,
            project::init_default_project,
            project::copy_file_to_project,
            project::extract_bgs_to_project,
            project::extract_bgm_to_project,
            project::get_engine_assets_dir,
            // Python 环境
            python_env::resolve_engine_env,
            python_env::ensure_engine_setup,
            python_env::run_script_output,
            // 图片
            media::get_sprite_thumbnail,
            media::pick_image_file,
            media::pick_files,
            media::pick_image_files,
            media::read_image_as_data_url,
            media::read_images_as_data_urls,
            // 打包
            pack::pack_bingo,
            pack::unpack_bingo,
            // 引擎进程
            engine::run_script,
            engine::stop_script,
            engine::send_stdin,
            engine::send_stdin_data,
            engine::run_script_file,
            // pip
            pip::pip_list_installed,
            pip::pip_list_all,
            pip::pip_install_package,
            pip::pip_uninstall_package,
            pip::pip_get_versions,
            pip::pip_check_outdated,
            pip::pip_upgrade_package,
            // shell
            shell::start_shell,
            shell::send_shell_input,
            shell::resize_shell,
            shell::stop_shell,
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    // 退出前落盘窗口尺寸，下次启动恢复
    app.run(|handle, event| {
        if matches!(event, RunEvent::Exit) {
            save_window_size(handle);
        }
    });
}
