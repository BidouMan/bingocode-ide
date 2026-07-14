use serde::{Deserialize, Serialize};
use std::io::Write;
use std::process::{Command, Stdio};
use std::sync::Mutex;
use tauri::Manager;

mod engine;
mod shell;

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
fn rename_path(old_path: String, new_path: String) -> Result<(), String> {
    std::fs::rename(&old_path, &new_path)
        .map_err(|e| format!("重命名失败: {}", e))
}

#[tauri::command]
fn path_exists(path: String) -> bool {
    std::path::Path::new(&path).exists()
}

#[tauri::command]
fn get_project_root() -> Result<String, String> {
    let cwd = std::env::current_dir()
        .map_err(|e| format!("Failed to get current dir: {}", e))?;
    // src-tauri 目录下需要向上一级到项目根目录
    let project_root = cwd.parent()
        .unwrap_or(&cwd)
        .to_string_lossy()
        .to_string();
    Ok(project_root)
}

#[tauri::command]
fn open_file_in_browser(path: String) -> Result<String, String> {
    // 检查文件是否存在
    let path_obj = std::path::Path::new(&path);
    if !path_obj.exists() {
        return Err(format!("文件不存在: {}", path));
    }

    let absolute_path = std::fs::canonicalize(path_obj)
        .map_err(|e| format!("获取绝对路径失败: {}", e))?
        .to_string_lossy()
        .to_string();

    // 使用系统默认应用打开文件
    #[cfg(target_os = "macos")]
    {
        let result = std::process::Command::new("open")
            .arg(&absolute_path)
            .output()
            .map_err(|e| format!("启动 open 命令失败: {}", e))?;

        if !result.status.success() {
            let stderr = String::from_utf8_lossy(&result.stderr);
            return Err(format!("open 命令执行失败: {}", stderr));
        }
    }
    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("cmd")
            .args(["/C", "start", "", &absolute_path])
            .spawn()
            .map_err(|e| format!("Failed to open file: {}", e))?;
    }
    #[cfg(target_os = "linux")]
    {
        std::process::Command::new("xdg-open")
            .arg(&absolute_path)
            .spawn()
            .map_err(|e| format!("Failed to open file: {}", e))?;
    }

    Ok(absolute_path)
}

#[tauri::command]
fn init_default_project() -> Result<String, String> {
    // 跨平台默认项目目录
    // Mac: ~/BingoCodeIDE/Projects/default
    // Windows: %USERPROFILE%\BingoCodeIDE\Projects\default
    let home = std::env::var("HOME").or_else(|_| std::env::var("USERPROFILE"))
        .map_err(|_| "Cannot find home directory".to_string())?;
    let project_root = std::path::PathBuf::from(&home)
        .join("BingoCodeIDE").join("Projects").join("default");

    // 启动时清理默认项目目录中的旧资源（保留目录结构）
    let _ = clean_default_project_assets(&project_root);

    // 创建项目目录结构
    let sprites_dir = project_root.join("assets").join("sprites");
    let maps_dir = project_root.join("assets").join("maps");
    let sounds_dir = project_root.join("assets").join("sounds");
    let code_dir = project_root.join("code");
    std::fs::create_dir_all(&sprites_dir).map_err(|e| e.to_string())?;
    std::fs::create_dir_all(&maps_dir).map_err(|e| e.to_string())?;
    std::fs::create_dir_all(&sounds_dir).map_err(|e| e.to_string())?;
    std::fs::create_dir_all(&code_dir).map_err(|e| e.to_string())?;

    Ok(project_root.to_string_lossy().to_string())
}

fn clean_default_project_assets(project_root: &std::path::Path) -> Result<(), String> {
    for subdir in &["assets/sprites", "assets/maps", "assets/sounds", "code"] {
        let dir = project_root.join(subdir);
        if dir.exists() {
            if let Ok(entries) = std::fs::read_dir(&dir) {
                for entry in entries.flatten() {
                    let path = entry.path();
                    if path.is_dir() {
                        let _ = std::fs::remove_dir_all(&path);
                    } else {
                        let _ = std::fs::remove_file(&path);
                    }
                }
            }
        }
    }
    // 清理临时脚本文件
    let _ = std::fs::remove_file(project_root.join(".temp_run.py"));
    Ok(())
}

#[tauri::command]
fn copy_file_to_project(src: String, project_root: String, relative_path: String) -> Result<String, String> {
    let dst = std::path::Path::new(&project_root).join(&relative_path);
    if let Some(parent) = dst.parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    std::fs::copy(&src, &dst).map_err(|e| format!("复制文件失败: {}", e))?;
    Ok(dst.to_string_lossy().to_string())
}

#[tauri::command]
fn extract_bgs_to_project(bgs_path: String, project_root: String, sprite_name: String) -> Result<String, String> {
    let target_dir = std::path::Path::new(&project_root)
        .join("assets").join("sprites").join(&sprite_name);
    std::fs::create_dir_all(&target_dir).map_err(|e| e.to_string())?;

    let data = std::fs::read(&bgs_path).map_err(|e| e.to_string())?;
    let mut zip = zip::ZipArchive::new(std::io::Cursor::new(data))
        .map_err(|e| format!("无法解析 .bgs 文件: {}", e))?;
    zip.extract(&target_dir)
        .map_err(|e| format!("解压 .bgs 失败: {}", e))?;

    Ok(target_dir.to_string_lossy().to_string())
}

#[tauri::command]
fn extract_bgm_to_project(bgm_path: String, project_root: String, map_name: String) -> Result<String, String> {
    let target_dir = std::path::Path::new(&project_root)
        .join("assets").join("maps").join(&map_name);
    std::fs::create_dir_all(&target_dir).map_err(|e| e.to_string())?;

    let data = std::fs::read(&bgm_path).map_err(|e| e.to_string())?;
    let mut zip = zip::ZipArchive::new(std::io::Cursor::new(data))
        .map_err(|e| format!("无法解析 .bgm 文件: {}", e))?;
    zip.extract(&target_dir)
        .map_err(|e| format!("解压 .bgm 失败: {}", e))?;

    Ok(target_dir.to_string_lossy().to_string())
}

#[tauri::command]
fn get_engine_assets_dir(app: tauri::AppHandle) -> Result<String, String> {
    let resource_dir = app.path().resource_dir().map_err(|e| e.to_string())?;

    // 查找引擎 assets 目录的策略（与 resolve_engine_env 相同）
    let engine_dir = if resource_dir.join("engine").exists() {
        resource_dir.join("engine")
    } else {
        let mut candidate = resource_dir.as_path();
        let mut found = None;
        for _ in 0..5 {
            if let Some(p) = candidate.parent() {
                candidate = p;
                let test = candidate.join("engine");
                if test.exists() {
                    found = Some(test);
                    break;
                }
            } else {
                break;
            }
        }
        if let Some(f) = found {
            f
        } else if let Ok(cwd) = std::env::current_dir() {
            cwd.join("engine")
        } else {
            resource_dir.join("engine")
        }
    };

    let assets_dir = engine_dir.join("assets");
    Ok(assets_dir.to_string_lossy().to_string())
}

#[tauri::command]
fn save_temp_script(project_dir: String, content: String) -> Result<String, String> {
    use std::io::Write;
    let dir = if project_dir.is_empty() {
        std::env::temp_dir()
    } else {
        std::path::PathBuf::from(&project_dir)
    };
    let temp_path = dir.join(".temp_run.py");
    if let Some(parent) = temp_path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| format!("创建临时目录失败: {}", e))?;
    }
    let mut file = std::fs::File::create(&temp_path).map_err(|e| format!("创建临时文件失败: {}", e))?;
    file.write_all(content.as_bytes()).map_err(|e| format!("写入临时文件失败: {}", e))?;
    file.sync_all().map_err(|e| format!("同步临时文件失败: {}", e))?;
    Ok(temp_path.to_str().ok_or("路径包含无效字符")?.to_string())
}

#[tauri::command]
fn cleanup_temp_script(project_dir: String) -> Result<(), String> {
    let dir = if project_dir.is_empty() {
        std::env::temp_dir()
    } else {
        std::path::PathBuf::from(&project_dir)
    };
    let temp_path = dir.join(".temp_run.py");
    if temp_path.exists() {
        std::fs::remove_file(&temp_path).map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
fn resolve_engine_env(app: tauri::AppHandle, script_path: String, project_root: Option<String>) -> Result<EngineEnv, String> {
    let resource_dir = app.path().resource_dir().map_err(|e| e.to_string())?;

    // 查找 engine 目录：从 resource_dir 往上逐级查找
    // engine 始终在源码仓库中，不在用户项目目录里
    let engine_dir = if resource_dir.join("engine").exists() {
        resource_dir.join("engine")
    } else {
        let mut candidate = resource_dir.as_path();
        let mut found = None;
        for _ in 0..5 {
            if let Some(p) = candidate.parent() {
                candidate = p;
                let test = candidate.join("engine");
                if test.exists() {
                    found = Some(test);
                    break;
                }
            } else {
                break;
            }
        }
        if let Some(f) = found {
            f
        } else if let Ok(cwd) = std::env::current_dir() {
            cwd.join("engine")
        } else {
            resource_dir.join("engine")
        }
    };

    let venv_python = if cfg!(target_os = "windows") {
        engine_dir.join("venv/Scripts/python.exe")
    } else {
        engine_dir.join("venv/bin/python3")
    };

    let python_path = if venv_python.exists() {
        venv_python.to_string_lossy().to_string()
    } else {
        // 在 engine_dir 的同级或上级查找 venv
        let mut candidate = engine_dir.as_path();
        let mut found_python = None;
        for _ in 0..3 {
            let venv_test = if cfg!(target_os = "windows") {
                candidate.join("engine/venv/Scripts/python.exe")
            } else {
                candidate.join("engine/venv/bin/python3")
            };
            if venv_test.exists() {
                found_python = Some(venv_test);
                break;
            }
            if let Some(p) = candidate.parent() {
                candidate = p;
            } else {
                break;
            }
        }
        if let Some(p) = found_python {
            p.to_string_lossy().to_string()
        } else if let Ok(cwd) = std::env::current_dir() {
            let cwd_venv = if cfg!(target_os = "windows") {
                cwd.join("engine/venv/Scripts/python.exe")
            } else {
                cwd.join("engine/venv/bin/python3")
            };
            if cwd_venv.exists() {
                cwd_venv.to_string_lossy().to_string()
            } else {
                find_system_python()?
            }
        } else {
            find_system_python()?
        }
    };

    let working_dir = project_root.clone().unwrap_or_else(|| {
        std::path::Path::new(&script_path)
            .parent()
            .map(|p| p.to_string_lossy().to_string())
            .unwrap_or_else(|| std::env::current_dir().unwrap().to_string_lossy().to_string())
    });

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

/// 确保引擎环境已设置（创建 venv 并安装依赖）
#[tauri::command]
fn ensure_engine_setup(engine_dir: String) -> Result<String, String> {
    let venv_dir = std::path::PathBuf::from(&engine_dir).join("venv");
    let venv_python = if cfg!(target_os = "windows") {
        venv_dir.join("Scripts/python.exe")
    } else {
        venv_dir.join("bin/python3")
    };

    // 如果 venv 已存在，直接返回
    if venv_python.exists() {
        return Ok(venv_python.to_string_lossy().to_string());
    }

    // 查找系统 Python
    let system_python = find_system_python()?;

    // 创建 venv
    let output = Command::new(&system_python)
        .args(["-m", "venv", venv_dir.to_str().unwrap_or("")])
        .output()
        .map_err(|e| format!("创建 venv 失败: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("创建 venv 失败: {}", stderr));
    }

    // 安装依赖
    let pip = if cfg!(target_os = "windows") {
        venv_dir.join("Scripts/pip.exe")
    } else {
        venv_dir.join("bin/pip")
    };
    let requirements = std::path::PathBuf::from(&engine_dir).join("requirements.txt");

    if requirements.exists() {
        let output = Command::new(&pip)
            .args(["install", "-r", requirements.to_str().unwrap_or("")])
            .output()
            .map_err(|e| format!("安装依赖失败: {}", e))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(format!("安装依赖失败: {}", stderr));
        }
    }

    Ok(venv_python.to_string_lossy().to_string())
}

#[derive(Debug, Serialize, Deserialize)]
pub struct EngineEnv {
    pub python_path: String,
    pub engine_dir: String,
    pub working_dir: String,
}

#[tauri::command]
fn pack_bingo(workspace_dir: String, output_path: String) -> Result<(), String> {
    use std::io::{Write, Read};
    use zip::write::FileOptions;

    let workspace = std::path::Path::new(&workspace_dir);
    if !workspace.exists() {
        return Err("工作目录不存在".to_string());
    }

    let output = std::path::Path::new(&output_path);
    if let Some(parent) = output.parent() {
        std::fs::create_dir_all(parent).map_err(|e| format!("创建目录失败: {}", e))?;
    }

    let file = std::fs::File::create(output)
        .map_err(|e| format!("创建 .bingo 文件失败: {}", e))?;
    let mut zip = zip::ZipWriter::new(file);
    let options = FileOptions::default()
        .compression_method(zip::CompressionMethod::Deflated)
        .compression_level(Some(6));

    // 递归添加工作目录中的所有文件
    fn add_dir_to_zip(
        zip: &mut zip::ZipWriter<std::fs::File>,
        base: &std::path::Path,
        current: &std::path::Path,
        options: zip::write::FileOptions,
    ) -> Result<(), String> {
        let entries = std::fs::read_dir(current)
            .map_err(|e| format!("读取目录失败: {}", e))?;

        for entry in entries.flatten() {
            let path = entry.path();
            let name = path.strip_prefix(base)
                .map_err(|e| format!("路径错误: {}", e))?
                .to_string_lossy()
                .to_string();

            if path.is_dir() {
                // 跳过隐藏目录和 __pycache__
                let dir_name = entry.file_name().to_string_lossy().to_string();
                if dir_name.starts_with('.') || dir_name == "__pycache__" {
                    continue;
                }
                add_dir_to_zip(zip, base, &path, options)?;
            } else {
                // 跳过隐藏文件和临时文件
                let file_name = entry.file_name().to_string_lossy().to_string();
                if file_name.starts_with('.') || file_name == ".temp_run.py" {
                    continue;
                }

                let mut f = std::fs::File::open(&path)
                    .map_err(|e| format!("打开文件失败 {}: {}", path.display(), e))?;
                let mut buffer = Vec::new();
                f.read_to_end(&mut buffer)
                    .map_err(|e| format!("读取文件失败: {}", e))?;

                zip.start_file(&name, options)
                    .map_err(|e| format!("创建 zip 条目失败: {}", e))?;
                zip.write_all(&buffer)
                    .map_err(|e| format!("写入 zip 失败: {}", e))?;
            }
        }
        Ok(())
    }

    add_dir_to_zip(&mut zip, workspace, workspace, options)?;
    zip.finish().map_err(|e| format!("完成 zip 写入失败: {}", e))?;

    Ok(())
}

#[tauri::command]
fn unpack_bingo(bingo_path: String, target_dir: String) -> Result<(), String> {
    let data = std::fs::read(&bingo_path)
        .map_err(|e| format!("读取 .bingo 文件失败: {}", e))?;
    let mut archive = zip::ZipArchive::new(std::io::Cursor::new(data))
        .map_err(|e| format!("解析 .bingo 文件失败: {}", e))?;

    let target = std::path::Path::new(&target_dir);
    std::fs::create_dir_all(target)
        .map_err(|e| format!("创建目标目录失败: {}", e))?;

    archive.extract(target)
        .map_err(|e| format!("解压 .bingo 文件失败: {}", e))?;

    Ok(())
}

#[tauri::command]
fn get_sprite_thumbnail(path: String) -> Result<String, String> {
    use std::io::Read;

    let config_str;
    let first_frame_name;
    let png_data;

    if path.ends_with(".bgm") {
        // 从 .bgm zip 文件读取缩略图 (thumbnail.png)
        let data = std::fs::read(&path).map_err(|e| format!("读取 .bgm 失败: {}", e))?;
        let mut archive = zip::ZipArchive::new(std::io::Cursor::new(data))
            .map_err(|e| format!("解析 zip 失败: {}", e))?;

        let mut thumb_buf = Vec::new();
        {
            let thumb_entry = archive.by_name("thumbnail.png")
                .map_err(|e| format!("thumbnail.png 不存在: {}", e))?;
            let mut reader = std::io::BufReader::new(thumb_entry);
            reader.read_to_end(&mut thumb_buf).map_err(|e| e.to_string())?;
        }
        png_data = thumb_buf;
    } else if path.ends_with(".bgs") {
        // 从 .bgs zip 文件读取第一帧
        let data = std::fs::read(&path).map_err(|e| format!("读取 .bgs 失败: {}", e))?;
        let mut archive = zip::ZipArchive::new(std::io::Cursor::new(data))
            .map_err(|e| format!("解析 zip 失败: {}", e))?;

        let mut config_buf = String::new();
        {
            let config_entry = archive.by_name("config.json")
                .map_err(|e| format!("config.json 不存在: {}", e))?;
            let mut reader = std::io::BufReader::new(config_entry);
            reader.read_to_string(&mut config_buf).map_err(|e| e.to_string())?;
        }
        config_str = config_buf;

        let config: serde_json::Value = serde_json::from_str(&config_str)
            .map_err(|e| format!("解析 config.json 失败: {}", e))?;
        let frames = config["frames"].as_array()
            .ok_or("config.json 中没有 frames 字段")?;
        first_frame_name = frames.first()
            .ok_or("frames 为空")?
            .as_str()
            .ok_or("frames[0] 不是字符串")?.to_string();

        let mut png_buf = Vec::new();
        {
            let mut png_entry = archive.by_name(&first_frame_name)
                .map_err(|e| format!("第一帧 {} 不存在: {}", first_frame_name, e))?;
            png_entry.read_to_end(&mut png_buf).map_err(|e| e.to_string())?;
        }
        png_data = png_buf;
    } else if path.ends_with(".png") || path.ends_with(".jpg") || path.ends_with(".jpeg")
        || path.ends_with(".gif") || path.ends_with(".bmp") || path.ends_with(".webp") {
        // 常规图片文件：直接读取
        png_data = std::fs::read(&path)
            .map_err(|e| format!("读取图片失败: {}", e))?;
    } else {
        // 从解压后的目录读取
        let config_path = format!("{}/config.json", path);
        config_str = std::fs::read_to_string(&config_path)
            .map_err(|e| format!("读取 config.json 失败: {}", e))?;

        let config: serde_json::Value = serde_json::from_str(&config_str)
            .map_err(|e| format!("解析 config.json 失败: {}", e))?;
        let frames = config["frames"].as_array()
            .ok_or("config.json 中没有 frames 字段")?;
        first_frame_name = frames.first()
            .ok_or("frames 为空")?
            .as_str()
            .ok_or("frames[0] 不是字符串")?.to_string();

        let frame_path = format!("{}/{}", path, first_frame_name);
        png_data = std::fs::read(&frame_path)
            .map_err(|e| format!("读取第一帧 {} 失败: {}", first_frame_name, e))?;
    }

    // 转为 base64 data URL
    use base64::Engine;
    let b64 = base64::engine::general_purpose::STANDARD.encode(&png_data);
    Ok(format!("data:image/png;base64,{}", b64))
}

#[tauri::command]
fn pick_image_file(app: tauri::AppHandle) -> Result<Option<String>, String> {
    use tauri_plugin_dialog::DialogExt;

    let path = app.dialog()
        .file()
        .add_filter("图片", &["png", "jpg", "jpeg", "bmp", "gif"])
        .blocking_pick_file();

    Ok(path.map(|p| p.to_string()))
}

#[tauri::command]
fn read_image_as_data_url(path: String) -> Result<String, String> {
    use base64::Engine;

    let data = std::fs::read(&path).map_err(|e| format!("读取图片失败: {}", e))?;

    // 根据扩展名判断 MIME 类型
    let mime = if path.ends_with(".jpg") || path.ends_with(".jpeg") {
        "image/jpeg"
    } else if path.ends_with(".bmp") {
        "image/bmp"
    } else if path.ends_with(".gif") {
        "image/gif"
    } else {
        "image/png"
    };

    let b64 = base64::engine::general_purpose::STANDARD.encode(&data);
    Ok(format!("data:{};base64,{}", mime, b64))
}

#[tauri::command]
fn run_script_output(
    working_dir: String,
    python_path: String,
    script_path: String,
) -> Result<String, String> {
    let output = Command::new(&python_path)
        .arg("-u")
        .arg(&script_path)
        .current_dir(&working_dir)
        .output()
        .map_err(|e| format!("Failed to run script: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();

    if !output.status.success() {
        return Err(format!("Script failed:\n{}", stderr));
    }

    Ok(stdout)
}

// ═══ 插件库 (pip) ═══

#[derive(Debug, Serialize, Deserialize)]
pub struct PipPackage {
    pub name: String,
    pub version: String,
}

/// 获取 venv 中已安装的包列表
#[tauri::command]
fn pip_list_installed(app: tauri::AppHandle) -> Result<Vec<PipPackage>, String> {
    let python_path = find_venv_python(&app)?;
    let output = Command::new(&python_path)
        .args(["-m", "pip", "list", "--format=json", "--not-required"])
        .output()
        .map_err(|e| format!("执行 pip list 失败: {}", e))?;

    if !output.status.success() {
        // --not-required 可能在旧版 pip 不支持，回退到不带该参数
        let output2 = Command::new(&python_path)
            .args(["-m", "pip", "list", "--format=json"])
            .output()
            .map_err(|e| format!("执行 pip list 失败: {}", e))?;
        let stdout = String::from_utf8_lossy(&output2.stdout).to_string();
        return parse_pip_list(&stdout);
    }

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    parse_pip_list(&stdout)
}

/// 获取 venv 中所有已安装包（含依赖）
#[tauri::command]
fn pip_list_all(app: tauri::AppHandle) -> Result<Vec<PipPackage>, String> {
    let python_path = find_venv_python(&app)?;
    let output = Command::new(&python_path)
        .args(["-m", "pip", "list", "--format=json"])
        .output()
        .map_err(|e| format!("执行 pip list 失败: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    parse_pip_list(&stdout)
}

fn parse_pip_list(json_str: &str) -> Result<Vec<PipPackage>, String> {
    let parsed: serde_json::Value = serde_json::from_str(json_str)
        .map_err(|e| format!("解析 pip list 输出失败: {}", e))?;

    let arr = parsed.as_array().ok_or("pip list 输出格式错误")?;
    let mut packages = Vec::new();
    for item in arr {
        if let (Some(name), Some(version)) = (item["name"].as_str(), item["version"].as_str()) {
            packages.push(PipPackage {
                name: name.to_string(),
                version: version.to_string(),
            });
        }
    }
    Ok(packages)
}

/// 安装包到 venv
#[tauri::command]
fn pip_install_package(
    app: tauri::AppHandle,
    package: String,
    version: Option<String>,
    mirror: String,
) -> Result<String, String> {
    let python_path = find_venv_python(&app)?;
    let spec = match version {
        Some(v) => format!("{}=={}", package, v),
        None => package,
    };

    let output = Command::new(&python_path)
        .args([
            "-m", "pip", "install",
            &spec,
            "-i", &mirror,
            "--no-warn-script-location",
        ])
        .output()
        .map_err(|e| format!("执行 pip install 失败: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();

    if !output.status.success() {
        return Err(format!("安装失败:\n{}", stderr));
    }

    Ok(stdout)
}

/// 卸载 venv 中的包
#[tauri::command]
fn pip_uninstall_package(
    app: tauri::AppHandle,
    package: String,
) -> Result<String, String> {
    let python_path = find_venv_python(&app)?;
    let output = Command::new(&python_path)
        .args(["-m", "pip", "uninstall", &package, "-y"])
        .output()
        .map_err(|e| format!("执行 pip uninstall 失败: {}", e))?;

    let stderr = String::from_utf8_lossy(&output.stderr).to_string();

    if !output.status.success() {
        return Err(format!("卸载失败:\n{}", stderr));
    }

    Ok(format!("已卸载 {}", package))
}

/// 获取指定包在 PyPI 上的可用版本
#[tauri::command]
fn pip_get_versions(
    package: String,
) -> Result<Vec<String>, String> {
    // 使用 PyPI JSON API 查询可用版本
    let url = format!("https://pypi.org/pypi/{}/json", package);
    let output = Command::new("curl")
        .args(["-s", "--max-time", "10", &url])
        .output()
        .map_err(|e| format!("查询版本失败: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    if stdout.is_empty() {
        return Err(format!("无法获取 {} 的版本信息", package));
    }

    let parsed: serde_json::Value = serde_json::from_str(&stdout)
        .map_err(|e| format!("解析版本信息失败: {}", e))?;

    let releases = parsed["releases"].as_object()
        .ok_or("版本信息格式错误")?;

    let mut versions: Vec<String> = releases.keys().cloned().collect();
    versions.sort_by(|a, b| {
        // 简单的版本倒序排列（最新的在前）
        b.cmp(a)
    });

    Ok(versions)
}

fn find_venv_python(app: &tauri::AppHandle) -> Result<String, String> {
    let env = resolve_engine_env(
        app.clone(),
        String::new(),
        None,
    )?;
    Ok(env.python_path)
}

#[derive(Debug, Serialize, Deserialize)]
pub struct OutdatedPackage {
    pub name: String,
    pub current_version: String,
    pub latest_version: String,
}

/// 检查所有可更新的包
#[tauri::command]
fn pip_check_outdated(app: tauri::AppHandle) -> Result<Vec<OutdatedPackage>, String> {
    let python_path = find_venv_python(&app)?;
    let output = Command::new(&python_path)
        .args(["-m", "pip", "list", "--outdated", "--format=json"])
        .output()
        .map_err(|e| format!("检查更新失败: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let parsed: serde_json::Value = serde_json::from_str(&stdout)
        .map_err(|e| format!("解析更新信息失败: {}", e))?;

    let arr = parsed.as_array().ok_or("更新信息格式错误")?;
    let mut packages = Vec::new();
    for item in arr {
        if let (Some(name), Some(ver), Some(latest)) = (
            item["name"].as_str(),
            item["version"].as_str(),
            item["latest_version"].as_str(),
        ) {
            packages.push(OutdatedPackage {
                name: name.to_string(),
                current_version: ver.to_string(),
                latest_version: latest.to_string(),
            });
        }
    }
    Ok(packages)
}

/// 升级单个包
#[tauri::command]
fn pip_upgrade_package(
    app: tauri::AppHandle,
    package: String,
    mirror: String,
) -> Result<String, String> {
    let python_path = find_venv_python(&app)?;
    let output = Command::new(&python_path)
        .args([
            "-m", "pip", "install", "--upgrade", &package,
            "-i", &mirror,
            "--no-warn-script-location",
        ])
        .output()
        .map_err(|e| format!("升级包失败: {}", e))?;

    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    if !output.status.success() {
        return Err(format!("升级失败:\n{}", stderr));
    }
    Ok(format!("{} 已升级", package))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_process::init())
        .manage(EngineState {
            process: Mutex::new(None),
        })
        .manage(ShellState {
            pty: Mutex::new(None),
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
            get_project_root,
            open_file_in_browser,
            save_temp_script,
            cleanup_temp_script,
            resolve_engine_env,
            ensure_engine_setup,
            init_default_project,
            copy_file_to_project,
            extract_bgs_to_project,
            extract_bgm_to_project,
            get_engine_assets_dir,
            get_sprite_thumbnail,
            pick_image_file,
            read_image_as_data_url,
            rename_path,
            pack_bingo,
            unpack_bingo,
            engine::run_script,
            engine::stop_script,
            engine::send_stdin,
            engine::run_script_file,
            run_script_output,
            pip_list_installed,
            pip_list_all,
            pip_install_package,
            pip_uninstall_package,
            pip_get_versions,
            pip_check_outdated,
            pip_upgrade_package,
            shell::start_shell,
            shell::send_shell_input,
            shell::resize_shell,
            shell::stop_shell,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
