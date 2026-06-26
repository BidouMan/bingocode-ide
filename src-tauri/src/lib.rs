use serde::{Deserialize, Serialize};
use std::process::{Command, Stdio};
use std::sync::Mutex;
use tauri::Manager;

mod engine;

pub struct EngineState {
    pub process: Mutex<Option<engine::RunningProcess>>,
}

#[tauri::command]
fn read_file(path: String) -> Result<String, String> {
    std::fs::read_to_string(&path).map_err(|e| format!("Failed to read file: {}", e))
}

#[tauri::command]
fn write_file(path: String, content: String) -> Result<(), String> {
    if let Some(parent) = std::path::Path::new(&path).parent() {
        std::fs::create_dir_all(parent).map_err(|e| format!("Failed to create directory: {}", e))?;
    }
    std::fs::write(&path, content).map_err(|e| format!("Failed to write file: {}", e))
}

#[tauri::command]
fn read_binary(path: String) -> Result<Vec<u8>, String> {
    std::fs::read(&path).map_err(|e| format!("Failed to read binary file: {}", e))
}

#[tauri::command]
fn write_binary(path: String, data: Vec<u8>) -> Result<(), String> {
    if let Some(parent) = std::path::Path::new(&path).parent() {
        std::fs::create_dir_all(parent).map_err(|e| format!("Failed to create directory: {}", e))?;
    }
    std::fs::write(&path, data).map_err(|e| format!("Failed to write binary file: {}", e))
}

#[tauri::command]
fn list_dir(path: String) -> Result<Vec<String>, String> {
    let entries = std::fs::read_dir(&path).map_err(|e| format!("Failed to read directory: {}", e))?;
    let mut result = Vec::new();
    for entry in entries {
        let entry = entry.map_err(|e| format!("Failed to read entry: {}", e))?;
        let name = entry.file_name().to_string_lossy().to_string();
        let is_dir = entry.file_type().map_err(|e| format!("Failed to get type: {}", e))?.is_dir();
        result.push(if is_dir {
            format!("{}/", name)
        } else {
            name
        });
    }
    result.sort();
    Ok(result)
}

#[tauri::command]
fn create_dir(path: String) -> Result<(), String> {
    std::fs::create_dir_all(&path).map_err(|e| format!("Failed to create directory: {}", e))
}

#[tauri::command]
fn delete_path(path: String) -> Result<(), String> {
    let p = std::path::Path::new(&path);
    if p.is_dir() {
        std::fs::remove_dir_all(&path).map_err(|e| format!("Failed to delete directory: {}", e))
    } else {
        std::fs::remove_file(&path).map_err(|e| format!("Failed to delete file: {}", e))
    }
}

#[tauri::command]
fn path_exists(path: String) -> bool {
    std::path::Path::new(&path).exists()
}

#[tauri::command]
fn resolve_engine_env(app: tauri::AppHandle, script_path: String) -> Result<EngineEnv, String> {
    let resource_dir = app.path().resource_dir().map_err(|e| e.to_string())?;

    let engine_dir = resource_dir.join("engine");
    let venv_python = if cfg!(target_os = "windows") {
        engine_dir.join("venv/Scripts/python.exe")
    } else {
        engine_dir.join("venv/bin/python3")
    };

    let python_path = if venv_python.exists() {
        venv_python.to_string_lossy().to_string()
    } else {
        find_system_python()?
    };

    let working_dir = std::path::Path::new(&script_path)
        .parent()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_else(|| std::env::current_dir().unwrap().to_string_lossy().to_string());

    Ok(EngineEnv {
        python_path,
        engine_dir: engine_dir.to_string_lossy().to_string(),
        working_dir,
    })
}

fn find_system_python() -> Result<String, String> {
    let names = if cfg!(target_os = "windows") {
        vec!["python", "python3"]
    } else {
        vec!["python3", "python"]
    };

    for name in names {
        if let Ok(output) = Command::new(name)
            .arg("--version")
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .output()
        {
            if output.status.success() {
                let path_output = if cfg!(target_os = "windows") {
                    Command::new("where").arg(name).output()
                } else {
                    Command::new("which").arg(name).output()
                };

                if let Ok(out) = path_output {
                    if out.status.success() {
                        let path = String::from_utf8_lossy(&out.stdout).trim().to_string();
                        if !path.is_empty() {
                            return Ok(path);
                        }
                    }
                }
            }
        }
    }
    Err("Python not found".to_string())
}

#[derive(Debug, Serialize, Deserialize)]
pub struct EngineEnv {
    pub python_path: String,
    pub engine_dir: String,
    pub working_dir: String,
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(EngineState {
            process: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![
            read_file,
            write_file,
            read_binary,
            write_binary,
            list_dir,
            create_dir,
            delete_path,
            path_exists,
            resolve_engine_env,
            engine::run_script,
            engine::stop_script,
            engine::send_stdin,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
