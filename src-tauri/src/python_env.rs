//! Python 运行环境：解析引擎目录/解释器、初始化依赖、运行脚本取输出。

use serde::{Deserialize, Serialize};
use std::process::Stdio;
use tauri::Manager;
use crate::fs_ops::{normalize_path_string, path_exists_impl};
use crate::hidden_command;

#[tauri::command]
pub(crate) fn resolve_engine_env(app: tauri::AppHandle, script_path: String, project_root: Option<String>) -> Result<EngineEnv, String> {
    let resource_dir = app.path().resource_dir().map_err(|e| e.to_string())?;
    let win = cfg!(target_os = "windows");
    let cwd = std::env::current_dir().unwrap_or_default();

    // 辅助函数：检查路径是否存在并返回可执行 Python 路径
    fn find_py(base: &std::path::Path, rel: &str) -> Option<String> {
        let p = base.join(rel);
        if path_exists_impl(&p) {
            Some(p.to_string_lossy().to_string())
        } else {
            None
        }
    }

    // 辅助函数：从某个目录往上找 engine 目录（含 bingo_engine.py）
    fn find_engine_dir(from: &std::path::Path) -> std::path::PathBuf {
        let mut cur = from;
        for _ in 0..6 {
            if path_exists_impl(&cur.join("bingo_engine.py")) || path_exists_impl(&cur.join("models")) {
                return cur.to_path_buf();
            }
            match cur.parent() {
                Some(p) => cur = p,
                None => break,
            }
        }
        from.to_path_buf()
    }

    let py_name = if win { "portable-python/python.exe" } else { "portable-python/bin/python3" };
    let venv_name = if win { "venv/Scripts/python.exe" } else { "venv/bin/python3" };

    // ═══ 查找 Python ═══
    // 打包后资源布局（tauri.conf.json 列表格式）：
    //   "../engine/portable-python/**/*" 中的 ../ 会被 Tauri 替换为 _up_/，
    //   实际路径: $RESOURCE/_up_/engine/portable-python/python.exe
    //
    // 这是 v0.4.8 ~ v0.5.1 "Python not found" 的根因：
    //   代码只查找 $RESOURCE/engine/portable-python/python.exe，
    //   但实际文件在 $RESOURCE/_up_/engine/portable-python/python.exe。
    //   macOS 上 resource_dir 是 Contents/Resources/，往上跳一级恰好能找到，
    //   所以 mac 版能成功；Windows 上 resource_dir 是安装根目录，往上跳找不到。
    //   v0.5.2 在查找路径中添加了 _up_ 前缀，两个平台都能正确找到。
    // dev 模式优先从源码树解析 Python（cwd 向上找 engine/）：
    // target/debug/_up_/ 是 Tauri 增量复制的资源副本，资源重组后残留旧文件，
    // 优先命中它会让游戏跑旧版引擎代码（如 bingo_engine.py 的修复不生效）
    #[cfg(debug_assertions)]
    let dev_py = {
        let mut found: Option<String> = None;
        let mut cur = cwd.as_path();
        for _ in 0..4 {
            let engine = cur.join("engine");
            if path_exists_impl(&engine.join("bingo_engine.py")) {
                for n in [&py_name, &venv_name] {
                    let p = engine.join(n);
                    if path_exists_impl(&p) {
                        found = Some(p.to_string_lossy().to_string());
                        break;
                    }
                }
                if found.is_some() { break; }
            }
            match cur.parent() {
                Some(p) => cur = p,
                None => break,
            }
        }
        found
    };
    #[cfg(not(debug_assertions))]
    let dev_py: Option<String> = None;

    let python_path = dev_py.or_else(|| {
    [
        // 1. 新布局：portable-python 直接放在 resource_dir 下（未来改用对象映射时）
        find_py(&resource_dir, &py_name),
        // 1b. engine 前缀
        find_py(&resource_dir, &format!("engine/{}", py_name)),
        // 2. 当前布局：_up_/engine/portable-python/（列表格式 ../ → _up_）
        find_py(&resource_dir, &format!("_up_/engine/{}", py_name)),
        // 3. resource_dir 同级 engine/（dev 模式）
        find_py(&resource_dir, &format!("../engine/{}", py_name)),
        // 4. 从 resource_dir 往上最多 4 级查找 portable-python
        (|| {
            let mut cur = resource_dir.as_path();
            for _ in 0..4 {
                cur = cur.parent()?;
                let p = cur.join("engine").join(&py_name);
                if path_exists_impl(&p) { return Some(p.to_string_lossy().to_string()); }
            }
            None
        })(),
        // 5. cwd/engine/（dev 模式）
        find_py(&cwd, &format!("engine/{}", py_name)),
        // 6. 从 cwd 往上最多 4 级查找 portable-python（dev 模式 cwd 可能是 src-tauri/）
        (|| {
            let mut cur = cwd.as_path();
            for _ in 0..4 {
                let p = cur.join("engine").join(&py_name);
                if path_exists_impl(&p) { return Some(p.to_string_lossy().to_string()); }
                cur = cur.parent()?;
            }
            None
        })(),
        // 7. venv 回退（开发环境）
        find_py(&resource_dir, &format!("engine/{}", venv_name)),
        find_py(&resource_dir, &venv_name),
        find_py(&cwd, &format!("engine/{}", venv_name)),
        // 8. 从 cwd 往上最多 4 级查找 venv（dev 模式 cwd 可能是 src-tauri/）
        (|| {
            let mut cur = cwd.as_path();
            for _ in 0..4 {
                let p = cur.join("engine").join(&venv_name);
                if path_exists_impl(&p) { return Some(p.to_string_lossy().to_string()); }
                let p2 = cur.join(&venv_name);
                if path_exists_impl(&p2) { return Some(p2.to_string_lossy().to_string()); }
                cur = cur.parent()?;
            }
            None
        })(),
        // 9. 从 resource_dir 往上查找 venv
        (|| {
            let mut cur = resource_dir.as_path();
            for _ in 0..6 {
                cur = cur.parent()?;
                let p = cur.join("engine").join(&venv_name);
                if path_exists_impl(&p) { return Some(p.to_string_lossy().to_string()); }
            }
            None
        })(),
    ].into_iter().flatten().next()
    });

    // ═══ 查找 engine_dir ═══
    let engine_dir = if let Some(ref py) = python_path {
        let py_path = std::path::Path::new(py);
        // 从 python 所在目录往上找 engine 目录
        let parent = py_path.parent().unwrap_or(&resource_dir);
        // portable-python/ 的上级可能是 engine/；venv/ 的上级也可能是 engine/
        let up = parent.parent().unwrap_or(parent);
        if path_exists_impl(&up.join("bingo_engine.py")) || path_exists_impl(&up.join("models")) {
            up.to_path_buf()
        } else if path_exists_impl(&parent.join("bingo_engine.py")) || path_exists_impl(&parent.join("models")) {
            parent.to_path_buf()
        } else {
            find_engine_dir(parent)
        }
    } else if path_exists_impl(&resource_dir.join("bingo_engine.py")) {
        resource_dir.clone()
    } else {
        find_engine_dir(&cwd)
    };

    let python_path = python_path.unwrap_or_default();

    if python_path.is_empty() {
        let checked = vec![
            resource_dir.join(&py_name),
            resource_dir.join(format!("engine/{}", py_name)),
            resource_dir.join(format!("_up_/engine/{}", py_name)),
            resource_dir.join(format!("../engine/{}", py_name)),
            cwd.join(format!("engine/{}", py_name)),
            resource_dir.join(format!("engine/{}", venv_name)),
            resource_dir.join(&venv_name),
            cwd.join(format!("engine/{}", venv_name)),
        ];
        let paths: Vec<String> = checked.iter().map(|p| format!("  {}", p.display())).collect();
        return Err(format!(
            "Python not found.\nresource_dir: {}\ncwd: {}\n已检查:\n{}",
            resource_dir.display(),
            cwd.display(),
            paths.join("\n")
        ));
    }

    let working_dir = project_root.clone().unwrap_or_else(|| {
        std::path::Path::new(&script_path)
            .parent()
            .map(|p| p.to_string_lossy().to_string())
            .unwrap_or_else(|| cwd.to_string_lossy().to_string())
    });

    Ok(EngineEnv {
        python_path,
        engine_dir: normalize_path_string(&engine_dir),
        working_dir: normalize_path_string(std::path::Path::new(&working_dir)),
    })
}

pub(crate) fn find_system_python() -> Result<String, String> {
    // Windows: 先尝试 py launcher，再尝试 python/python3
    // macOS/Linux: 先尝试 python3，再尝试 python
    let names = if cfg!(target_os = "windows") {
        vec!["py", "python", "python3"]
    } else {
        vec!["python3", "python"]
    };

    for name in names {
        if let Ok(output) = hidden_command(name)
            .arg("--version")
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .output()
        {
            if output.status.success() {
                let path_output = if cfg!(target_os = "windows") {
                    hidden_command("where").arg(name).output()
                } else {
                    hidden_command("which").arg(name).output()
                };

                if let Ok(out) = path_output {
                    if out.status.success() {
                        let path = String::from_utf8_lossy(&out.stdout).trim().to_string();
                        if !path.is_empty() {
                            // py launcher 返回的是 launcher 路径，需要获取实际 Python 路径
                            if name == "py" {
                                if let Ok(ver_output) = hidden_command("py")
                                    .args(["-3", "-c", "import sys; print(sys.executable)"])
                                    .stdout(Stdio::piped())
                                    .stderr(Stdio::piped())
                                    .output()
                                {
                                    if ver_output.status.success() {
                                        let real_path = String::from_utf8_lossy(&ver_output.stdout).trim().to_string();
                                        if !real_path.is_empty() {
                                            return Ok(real_path);
                                        }
                                    }
                                }
                            }
                            return Ok(path);
                        }
                    }
                }
            }
        }
    }

    // Windows: 尝试常见安装路径
    if cfg!(target_os = "windows") {
        if let Ok(app_data) = std::env::var("LOCALAPPDATA") {
            let candidates = [
                format!("{}\\Programs\\Python\\Python312\\python.exe", app_data),
                format!("{}\\Programs\\Python\\Python311\\python.exe", app_data),
                format!("{}\\Programs\\Python\\Python310\\python.exe", app_data),
                format!("{}\\Programs\\Python\\Python3\\python.exe", app_data),
            ];
            for path in &candidates {
                if std::path::Path::new(path).exists() {
                    return Ok(path.clone());
                }
            }
        }
    }

    Err("Python not found".to_string())
}

/// 确保引擎环境已设置（优先使用便携 Python，回退到 venv）
#[tauri::command]
pub(crate) fn ensure_engine_setup(engine_dir: String) -> Result<String, String> {
    let engine_path = std::path::Path::new(&engine_dir);

    // 优先使用便携 Python（打包版本自带）
    let portable_python = if cfg!(target_os = "windows") {
        engine_path.join("portable-python/python.exe")
    } else {
        engine_path.join("portable-python/bin/python3")
    };
    if portable_python.exists() {
        return Ok(normalize_path_string(&portable_python));
    }

    // 回退：使用 venv（本地开发环境）
    let venv_dir = engine_path.join("venv");
    let venv_python = if cfg!(target_os = "windows") {
        venv_dir.join("Scripts/python.exe")
    } else {
        venv_dir.join("bin/python3")
    };

    if venv_python.exists() {
        return Ok(venv_python.to_string_lossy().to_string());
    }

    // 查找系统 Python 来创建 venv
    let system_python = find_system_python()?;

    // 创建 venv
    let output = hidden_command(&system_python)
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
    let requirements = engine_path.join("requirements.txt");

    if requirements.exists() {
        let output = hidden_command(&pip)
            .args(["install", "-r", requirements.to_str().unwrap_or("")])
            .output()
            .map_err(|e| format!("安装依赖失败: {}", e))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(format!("安装依赖失败: {}", stderr));
        }
    }

    Ok(normalize_path_string(&venv_python))
}

#[derive(Debug, Serialize, Deserialize)]
pub(crate) struct EngineEnv {
    pub python_path: String,
    pub engine_dir: String,
    pub working_dir: String,
}

#[tauri::command]
pub(crate) fn run_script_output(
    working_dir: String,
    python_path: String,
    script_path: String,
) -> Result<String, String> {
    let output = hidden_command(&python_path)
        .arg("-u")
        .arg(&script_path)
        .current_dir(&working_dir)
        .env("PYTHONIOENCODING", "utf-8")
        .env("PYTHONUNBUFFERED", "1")
        .output()
        .map_err(|e| format!("Failed to run script: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();

    if !output.status.success() {
        return Err(format!("Script failed:\n{}", stderr));
    }

    Ok(stdout)
}
