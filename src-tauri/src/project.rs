//! 项目相关命令：默认项目初始化、素材导入项目、临时脚本、引擎资源目录。

use crate::fs_ops::{normalize_path_string, path_exists_impl, remove_path_retry};
use tauri::Manager;

#[tauri::command]
pub(crate) fn init_default_project() -> Result<String, String> {
    // 跨平台默认项目目录
    // Mac: ~/BingoCodeIDE/Projects/default
    // Windows: %USERPROFILE%\BingoCodeIDE\Projects\default
    let home = user_home_dir()?;
    let project_root = home.join("BingoCodeIDE").join("Projects").join("default");

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

/// 用户主目录。
/// Windows 上优先 USERPROFILE：HOME 可能被 Git 等工具设成空串或 /c/Users/... 形式，
/// 空串会让项目目录退化成「相对当前工作目录」，跑到安装目录或桌面附近去。
fn user_home_dir() -> Result<std::path::PathBuf, String> {
    let keys: &[&str] = if cfg!(windows) {
        &["USERPROFILE", "HOME"]
    } else {
        &["HOME"]
    };
    for key in keys {
        let Ok(value) = std::env::var(key) else { continue };
        let value = value.trim();
        if value.is_empty() {
            continue;
        }
        let path = std::path::PathBuf::from(value);
        if path.is_absolute() {
            return Ok(path);
        }
    }
    Err("Cannot find home directory".to_string())
}

fn clean_default_project_assets(project_root: &std::path::Path) -> Result<(), String> {
    for subdir in &["assets/sprites", "assets/maps", "assets/sounds", "code"] {
        let dir = project_root.join(subdir);
        if dir.exists() {
            if let Ok(entries) = std::fs::read_dir(&dir) {
                for entry in entries.flatten() {
                    let path = entry.path();
                    remove_path_retry(&path);
                }
            }
        }
    }
    // 清理临时脚本文件
    remove_path_retry(&project_root.join(".temp_run.py"));
    Ok(())
}

#[tauri::command]
pub(crate) fn copy_file_to_project(src: String, project_root: String, relative_path: String) -> Result<String, String> {
    let dst = std::path::Path::new(&project_root).join(&relative_path);
    if let Some(parent) = dst.parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    std::fs::copy(&src, &dst).map_err(|e| format!("复制文件失败: {}", e))?;
    Ok(dst.to_string_lossy().to_string())
}

#[tauri::command]
pub(crate) fn extract_bgs_to_project(bgs_path: String, project_root: String, sprite_name: String) -> Result<String, String> {
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
pub(crate) fn extract_bgm_to_project(bgm_path: String, project_root: String, map_name: String) -> Result<String, String> {
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
pub(crate) fn get_engine_assets_dir(app: tauri::AppHandle) -> Result<String, String> {
    let resource_dir = app.path().resource_dir().map_err(|e| e.to_string())?;

    // dev 模式优先用源码树的 engine/assets：
    // target/debug/_up_/ 是 Tauri 增量复制的资源副本，资源目录重组后会残留旧结构
    // （如 sprites/images、sprites/packages），命中它会让内置精灵库扫出过期分类
    #[cfg(debug_assertions)]
    {
        if let Ok(cwd) = std::env::current_dir() {
            let mut cur = cwd.as_path();
            for _ in 0..4 {
                let test = cur.join("engine");
                if path_exists_impl(&test.join("assets")) || path_exists_impl(&test.join("bingo_engine.py")) {
                    return Ok(normalize_path_string(&test.join("assets")));
                }
                match cur.parent() {
                    Some(p) => cur = p,
                    None => break,
                }
            }
        }
    }

    // 打包后资源布局（tauri.conf.json 列表格式）：
    //   "../engine/assets/**/*" 中的 ../ 会被 Tauri 替换为 _up_/，
    //   实际路径: $RESOURCE/_up_/engine/assets/
    //
    // dev 模式下 resource_dir 可能指向 src-tauri/，需要往上找项目根的 engine/
    let candidates = [
        resource_dir.join("engine"),
        resource_dir.join("_up_").join("engine"),
        resource_dir.join("..").join("engine"),
    ];

    for c in &candidates {
        if path_exists_impl(&c.join("assets")) || path_exists_impl(&c.join("bingo_engine.py")) {
            let assets_dir = c.join("assets");
            return Ok(normalize_path_string(&assets_dir));
        }
    }

    // 从 resource_dir 往上找
    let mut cur = resource_dir.as_path();
    for _ in 0..5 {
        if let Some(p) = cur.parent() {
            cur = p;
            let test = cur.join("engine");
            if path_exists_impl(&test.join("assets")) || path_exists_impl(&test.join("bingo_engine.py")) {
                return Ok(normalize_path_string(&test.join("assets")));
            }
        } else {
            break;
        }
    }

    // dev 模式：从 cwd 找
    if let Ok(cwd) = std::env::current_dir() {
        let mut cur = cwd.as_path();
        for _ in 0..4 {
            let test = cur.join("engine");
            if path_exists_impl(&test.join("assets")) || path_exists_impl(&test.join("bingo_engine.py")) {
                return Ok(normalize_path_string(&test.join("assets")));
            }
            match cur.parent() {
                Some(p) => cur = p,
                None => break,
            }
        }
    }

    // 最终回退
    Ok(normalize_path_string(&resource_dir.join("engine").join("assets")))
}

#[tauri::command]
pub(crate) fn save_temp_script(project_dir: String, content: String) -> Result<String, String> {
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
pub(crate) fn cleanup_temp_script(project_dir: String) -> Result<(), String> {
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
