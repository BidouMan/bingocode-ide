//! 文件系统命令：读写/目录/删除/重命名/复制/路径判断/在浏览器打开。


#[tauri::command]
pub(crate) fn read_file(path: String) -> Result<String, String> {
    std::fs::read_to_string(&path).map_err(|e| format!("Failed to read file: {}", e))
}

#[tauri::command]
pub(crate) fn write_file(path: String, content: String) -> Result<(), String> {
    if let Some(parent) = std::path::Path::new(&path).parent() {
        std::fs::create_dir_all(parent).map_err(|e| format!("Failed to create directory: {}", e))?;
    }
    std::fs::write(&path, content).map_err(|e| format!("Failed to write file: {}", e))
}

#[tauri::command]
pub(crate) fn read_binary(path: String) -> Result<Vec<u8>, String> {
    std::fs::read(&path).map_err(|e| format!("Failed to read binary file: {}", e))
}

#[tauri::command]
pub(crate) fn write_binary(path: String, data: Vec<u8>) -> Result<(), String> {
    if let Some(parent) = std::path::Path::new(&path).parent() {
        std::fs::create_dir_all(parent).map_err(|e| format!("Failed to create directory: {}", e))?;
    }
    std::fs::write(&path, data).map_err(|e| format!("Failed to write binary file: {}", e))
}

#[tauri::command]
pub(crate) fn list_dir(path: String) -> Result<Vec<String>, String> {
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
pub(crate) fn create_dir(path: String) -> Result<(), String> {
    std::fs::create_dir_all(&path).map_err(|e| format!("Failed to create directory: {}", e))
}

#[tauri::command]
pub(crate) fn delete_path(path: String) -> Result<(), String> {
    let p = std::path::Path::new(&path);
    if p.is_dir() {
        std::fs::remove_dir_all(&path).map_err(|e| format!("Failed to delete directory: {}", e))
    } else {
        std::fs::remove_file(&path).map_err(|e| format!("Failed to delete file: {}", e))
    }
}

#[tauri::command]
pub(crate) fn rename_path(old_path: String, new_path: String) -> Result<(), String> {
    std::fs::rename(&old_path, &new_path)
        .map_err(|e| format!("重命名失败: {}", e))
}

#[tauri::command]
pub(crate) fn copy_file(src: String, dst_dir: String) -> Result<String, String> {
    let src_path = std::path::Path::new(&src);
    let file_name = src_path.file_name()
        .ok_or_else(|| "无法获取文件名".to_string())?;
    let dst_path = std::path::Path::new(&dst_dir).join(file_name);
    // 如果目标已存在，加后缀避免覆盖
    let final_path = if dst_path.exists() {
        let stem = src_path.file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("file");
        let ext = src_path.extension()
            .and_then(|s| s.to_str())
            .map(|e| format!(".{}", e))
            .unwrap_or_default();
        let mut i = 1;
        loop {
            let candidate = std::path::Path::new(&dst_dir).join(format!("{}_{}{}", stem, i, ext));
            if !candidate.exists() {
                break candidate;
            }
            i += 1;
        }
    } else {
        dst_path
    };
    std::fs::copy(&src, &final_path)
        .map_err(|e| format!("复制文件失败: {}", e))?;
    final_path.to_str()
        .map(|s| s.to_string())
        .ok_or_else(|| "路径转换失败".to_string())
}

// Windows: 去掉 \\?\ 扩展前缀。Tauri resource_dir 在 Windows 上可能返回带此前缀的路径，
// 而 \\?\ 路径下 Win32 不再规范化混合分隔符，前端用 / 拼接的子路径会全部失效；
// 同时 C:\Users 的 \U 等进入 Python 字符串字面量会触发 Unicode 转义错误
pub(crate) fn normalize_path_string(p: &std::path::Path) -> String {
    p.to_string_lossy()
        .trim_start_matches("\\\\?\\")
        .to_string()
}

// Windows: 去掉 \\?\ 前缀再检查，否则 Path::exists() 可能失败
pub(crate) fn path_exists_impl(p: &std::path::Path) -> bool {
    if cfg!(windows) {
        std::path::PathBuf::from(normalize_path_string(p)).exists()
    } else {
        p.exists()
    }
}

#[tauri::command]
pub(crate) fn path_exists(path: String) -> bool {
    path_exists_impl(std::path::Path::new(&path))
}

#[tauri::command]
pub(crate) fn get_project_root() -> Result<String, String> {
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
pub(crate) fn open_file_in_browser(path: String) -> Result<String, String> {
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
