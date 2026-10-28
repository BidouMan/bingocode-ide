use std::io::Write;
use std::process::Command;
use std::sync::Mutex;

mod engine;
mod fs_ops;
mod media;
mod pack;
mod pip;
mod project;
mod python_env;
mod shell;

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
    tauri::Builder::default()
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
            fs_ops::get_project_root,
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
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
